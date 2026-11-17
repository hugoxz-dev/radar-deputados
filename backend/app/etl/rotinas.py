"""Rotinas do ETL: juntam extrair -> transformar -> carregar.

Ficam separadas do __main__.py (a linha de comando) para que o agendador
(scheduler.py) possa chamar as mesmas funções.
"""

import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.etl import carregar, extrair, transformar
from app.etl.execucao import Progresso, registrar_execucao
from app.models import Deputado, Despesa, ResumoIA
from app.services import notificacoes, resumo_ia
from app.services.anomalias import calcular_alertas
from app.services.camara_client import CamaraClient
from app.services.periodo import Periodo

log = logging.getLogger(__name__)


def _atualizar_deputados(db: Session, cliente: CamaraClient) -> list[dict]:
    """Baixa e grava a lista de deputados; busca o nome civil só de quem ainda não tem."""
    legislatura, brutos = extrair.extrair_deputados(cliente)
    linhas = [transformar.transformar_deputado(d, legislatura, d["_em_exercicio"]) for d in brutos]
    carregar.upsert_deputados(db, linhas)
    db.commit()

    faltando = carregar.ids_sem_nome_civil(db)
    if faltando:
        log.info("Buscando nome civil de %d deputados...", len(faltando))
        nomes = extrair.extrair_nomes_civis(cliente, faltando, get_settings().etl_paralelismo)
        carregar.gravar_nomes_civis(db, nomes)
        db.commit()
    return linhas


def _coletar_despesas(
    db: Session,
    cliente: CamaraClient,
    ids_deputados: list[int],
    periodos: list[tuple[int, int]],
    progresso: Progresso,
) -> None:
    """Baixa e sincroniza as despesas, gravando (commit) deputado a deputado.

    Commit por deputado: se a execução cair no meio, o que já foi carregado
    fica salvo, e rodar de novo simplesmente continua (é idempotente).
    """
    total = len(ids_deputados)
    inicio = time.monotonic()
    log.info("Coletando despesas de %d deputados, períodos %s a %s", total, periodos[0], periodos[-1])

    resultados = extrair.extrair_despesas(cliente, ids_deputados, periodos, get_settings().etl_paralelismo)
    for n, (id_deputado, brutas, erro) in enumerate(resultados, start=1):
        if erro is not None:
            log.error("Deputado %d: falhou (%s)", id_deputado, erro)
            progresso.avisos.append(f"deputado {id_deputado}: {erro[:150]}")
            continue
        linhas = transformar.transformar_despesas(brutas, id_deputado)
        gravadas, removidas = carregar.sincronizar_despesas(db, id_deputado, periodos, linhas)
        db.commit()
        progresso.registros += gravadas
        if removidas:
            log.info("Deputado %d: %d notas removidas (não constam mais na API)", id_deputado, removidas)
        if n % 25 == 0 or n == total:
            log.info("  %d/%d deputados (%.0fs)", n, total, time.monotonic() - inicio)


def carga_inicial(meses: int | None = None, limite_deputados: int | None = None, uf: str | None = None) -> None:
    """Deputados da legislatura atual + despesas dos últimos N meses."""
    meses = meses or get_settings().etl_meses_carga_inicial
    periodos = extrair.periodos_ultimos_meses(meses)
    with registrar_execucao("carga-inicial") as progresso, CamaraClient() as cliente, SessionLocal() as db:
        deputados = _atualizar_deputados(db, cliente)
        if uf:
            deputados = [d for d in deputados if d["uf"] == uf.upper()]
        ids = sorted(d["id"] for d in deputados)[:limite_deputados]
        _coletar_despesas(db, cliente, ids, periodos, progresso)


def atualizar() -> None:
    """Atualização incremental: só o mês atual e o anterior.

    O anterior entra porque as notas chegam com atraso (o deputado tem
    até 90 dias para apresentar a nota). Os deputados consultados são os
    em exercício + quem teve despesa nesses meses (ex.: suplente que saiu).
    """
    periodos = extrair.periodos_ultimos_meses(2)
    with registrar_execucao("atualizar") as progresso, CamaraClient() as cliente, SessionLocal() as db:
        _atualizar_deputados(db, cliente)
        ids = deputados_para_atualizar(db, periodos[0])
        _coletar_despesas(db, cliente, ids, periodos, progresso)


def recalcular_alertas(notificar: bool = True) -> list[int]:
    """Roda as 4 regras sobre todas as despesas do banco e sincroniza a tabela de alertas.

    Depois, envia e-mail aos assinantes Pro com os alertas NOVOS que batem com as
    inscrições deles. Retorna os ids dos alertas novos.
    """
    with registrar_execucao("recalcular-alertas") as progresso, SessionLocal() as db:
        df = carregar.carregar_despesas_para_analise(db)
        log.info("Analisando %d despesas...", len(df))
        alertas = calcular_alertas(df, get_settings())
        por_regra = Counter(a.regra for a in alertas)
        log.info("Alertas calculados: %d %s", len(alertas), dict(por_regra))

        novos, removidos = carregar.gravar_alertas(db, alertas)
        db.commit()
        progresso.registros = len(alertas)
        log.info("%d novos, %d removidos (não se aplicam mais)", len(novos), removidos)

        # Depois do commit: se o envio falhar, os alertas continuam gravados.
        if notificar and novos:
            notificacoes.notificar_novos_alertas(db, novos, get_settings())
        return novos


def ciclo_diario() -> None:
    """O que o agendador roda todo dia: dados novos -> alertas -> e-mails -> resumos que faltam.

    Cada etapa registra a própria execução em execucoes_etl. Se uma falhar, as
    seguintes ainda rodam (com os dados que já existem) e o erro fica no log.
    """
    for nome, etapa in [
        ("atualizar", atualizar),
        ("recalcular-alertas", recalcular_alertas),
        ("gerar-resumos", gerar_resumos),
    ]:
        try:
            etapa()
        except Exception:  # noqa: BLE001 - uma etapa com erro não impede as outras
            log.exception("Etapa %s do ciclo diário falhou; seguindo para a próxima.", nome)


def gerar_resumos(limite: int | None = None, deputado_id: int | None = None, forcar: bool = False) -> int:
    """Gera o resumo em linguagem simples de cada deputado com gastos nos últimos 12 meses.

    - Um resumo por deputado e período: quem já tem não é gerado de novo (cache),
      a não ser com forcar=True.
    - Os dados são montados no banco (thread principal); as chamadas ao LLM, que
      demoram, rodam em paralelo; a gravação volta para a thread principal.
    """
    cfg = get_settings()
    provedor = resumo_ia.obter_provedor(cfg)
    periodo = Periodo.ultimos_meses(12)

    with registrar_execucao("gerar-resumos") as progresso, SessionLocal() as db:
        com_gasto = select(Despesa.deputado_id).where(periodo.filtro(Despesa.ano, Despesa.mes)).distinct()
        consulta = select(Deputado).where(Deputado.id.in_(com_gasto)).order_by(Deputado.id)
        if deputado_id:
            consulta = consulta.where(Deputado.id == deputado_id)
        if not forcar:
            ja_tem = select(ResumoIA.deputado_id).where(ResumoIA.periodo == periodo.chave)
            consulta = consulta.where(Deputado.id.not_in(ja_tem))
        deputados = list(db.scalars(consulta.limit(limite)))
        log.info("Gerando %d resumos (%s, período %s)...", len(deputados), provedor.nome_modelo, periodo.chave)

        dados = {d.id: resumo_ia.montar_dados(db, d, periodo) for d in deputados}
        with ThreadPoolExecutor(max_workers=cfg.llm_paralelismo) as pool:
            textos = pool.map(lambda d: resumo_ia.gerar_texto(provedor, d), dados.values())
            resultados = dict(zip(dados.keys(), textos, strict=True))

        for id_deputado, (texto, modelo) in resultados.items():
            stmt = insert(ResumoIA).values(
                deputado_id=id_deputado, periodo=periodo.chave, texto=texto, modelo_usado=modelo
            )
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=[ResumoIA.deputado_id, ResumoIA.periodo],
                    set_={
                        "texto": stmt.excluded.texto,
                        "modelo_usado": stmt.excluded.modelo_usado,
                        "gerado_em": func.now(),
                    },
                )
            )
        db.commit()
        progresso.registros = len(resultados)
        log.info("Resumos gravados: %s", dict(Counter(modelo for _, modelo in resultados.values())))
        return len(resultados)


def deputados_para_atualizar(db: Session, desde: tuple[int, int]) -> list[int]:
    """Em exercício + quem tem despesa a partir de `desde` (ano, mes)."""
    em_exercicio = set(db.scalars(select(Deputado.id).where(Deputado.em_exercicio)))
    # Comparação de tupla do SQL: (ano, mes) >= (2026, 10) compara ano e, se empatar, mês.
    # (Calcular ano*100+mes estouraria o tipo smallint das colunas.)
    com_despesa = set(
        db.scalars(select(Despesa.deputado_id).where(tuple_(Despesa.ano, Despesa.mes) >= tuple_(*desde)).distinct())
    )
    return sorted(em_exercicio | com_despesa)
