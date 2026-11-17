"""Etapa E do ETL: busca os dados na API da Câmara.

Por que a API e não os arquivos CSV anuais da Câmara?
Comparamos as duas fontes (nov/2026). O CSV anual
(https://www.camara.leg.br/cotas/Ano-AAAA.csv.zip) seria mais rápido (um
download por ano), mas NÃO traz a categoria "PASSAGEM AÉREA - SIGEPA", que
na amostra era ~25% das notas. Como a especificação pede a API como fonte
única e o CSV sairia incompleto, usamos a API com downloads em paralelo.
Detalhes em docs/arquitetura.md.
"""

import logging
from collections import defaultdict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from app.services.camara_client import CamaraClient

log = logging.getLogger(__name__)


def periodos_ultimos_meses(quantidade: int, hoje: date | None = None) -> list[tuple[int, int]]:
    """Os últimos N meses até o mês atual (inclusive), do mais antigo ao mais novo.

    >>> periodos_ultimos_meses(3, date(2026, 2, 10))
    [(2025, 12), (2026, 1), (2026, 2)]
    """
    hoje = hoje or date.today()
    # Truque: numerar os meses em sequência (ano*12 + mês) torna "voltar N meses"
    # uma simples subtração, sem tratar a virada de ano à parte.
    indice_atual = hoje.year * 12 + (hoje.month - 1)
    periodos = []
    for indice in range(indice_atual - quantidade + 1, indice_atual + 1):
        ano, mes_zero = divmod(indice, 12)
        periodos.append((ano, mes_zero + 1))
    return periodos


def agrupar_por_ano(periodos: list[tuple[int, int]]) -> dict[int, list[int]]:
    """[(2025, 12), (2026, 1)] -> {2025: [12], 2026: [1]}: uma consulta por ano."""
    por_ano: dict[int, list[int]] = defaultdict(list)
    for ano, mes in periodos:
        por_ano[ano].append(mes)
    return dict(por_ano)


def extrair_deputados(cliente: CamaraClient) -> tuple[int, list[dict]]:
    """Todos os deputados da legislatura atual, marcando quem está em exercício.

    Pegamos a legislatura inteira (inclui suplentes que já saíram) para não
    perder as despesas de quem exerceu mandato em parte do período.
    """
    legislatura = cliente.legislatura_atual()
    da_legislatura = cliente.listar_deputados(legislatura)
    em_exercicio = cliente.listar_deputados()  # sem filtro = só quem está no cargo hoje
    ids_exercicio = {d["id"] for d in em_exercicio}

    # Um deputado pode aparecer mais de uma vez (ex.: trocou de partido).
    # Ficamos com o registro de "em exercício", que tem o partido atual.
    por_id: dict[int, dict] = {d["id"]: d for d in da_legislatura}
    por_id.update({d["id"]: d for d in em_exercicio})
    for d in por_id.values():
        d["_em_exercicio"] = d["id"] in ids_exercicio

    log.info("Legislatura %d: %d deputados (%d em exercício)", legislatura, len(por_id), len(ids_exercicio))
    return legislatura, list(por_id.values())


def extrair_nomes_civis(cliente: CamaraClient, ids: list[int], paralelismo: int) -> dict[int, str]:
    """nomeCivil só vem no detalhe do deputado (uma requisição por deputado)."""
    nomes: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=paralelismo) as pool:
        futuros = {pool.submit(cliente.detalhar_deputado, i): i for i in ids}
        for futuro in as_completed(futuros):
            try:
                nomes[futuros[futuro]] = futuro.result().get("nomeCivil")
            except Exception as erro:  # noqa: BLE001 - nome civil é opcional; segue sem ele
                log.warning("Sem nome civil do deputado %s: %s", futuros[futuro], erro)
    return nomes


def extrair_despesas(
    cliente: CamaraClient,
    ids_deputados: list[int],
    periodos: list[tuple[int, int]],
    paralelismo: int,
) -> Iterator[tuple[int, list[dict] | None, str | None]]:
    """Baixa as despesas de vários deputados em paralelo.

    Entrega (id_deputado, despesas, erro) à medida que cada um termina, para o
    carregamento acontecer em seguida, sem esperar todos. Se um deputado falhar,
    entrega erro e o ETL continua com os demais.

    Por que threads? O tempo é quase todo espera de rede; com 3 downloads
    simultâneos a carga cai de ~20 para ~7 minutos, sem sobrecarregar a API.
    """
    por_ano = agrupar_por_ano(periodos)

    def baixar(id_deputado: int) -> list[dict]:
        despesas: list[dict] = []
        for ano, meses in por_ano.items():
            despesas.extend(cliente.listar_despesas(id_deputado, ano, meses))
        return despesas

    with ThreadPoolExecutor(max_workers=paralelismo) as pool:
        futuros = {pool.submit(baixar, i): i for i in ids_deputados}
        for futuro in as_completed(futuros):
            id_deputado = futuros[futuro]
            try:
                yield id_deputado, futuro.result(), None
            except Exception as erro:  # noqa: BLE001
                yield id_deputado, None, str(erro)
