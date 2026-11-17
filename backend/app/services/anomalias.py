"""Detecção de gastos fora do padrão: quatro regras estatísticas.

LINGUAGEM: um alerta é um DESTAQUE ESTATÍSTICO ("gasto fora do padrão",
"atípico"). Nunca indica irregularidade. Os textos gerados aqui seguem isso.

Cada regra é uma função PURA: recebe um DataFrame de despesas e devolve
uma lista de AlertaCalculado. Não toca no banco. Por isso dá para testar
cada regra com meia dúzia de linhas inventadas (tests/test_anomalias.py).

Colunas esperadas no DataFrame (ver carregar_despesas):
    id, deputado_id, uf, categoria_id, categoria_slug, categoria_nome,
    fornecedor_id, fornecedor_nome, ano, mes, data_documento, valor

Os parâmetros foram calibrados com os dados reais (nov/2026); a justificativa
de cada escolha está em docs/metodologia.md.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.config import Settings

# Fator que torna o MAD comparável ao desvio-padrão numa distribuição normal
# (z-score modificado de Iglewicz e Hoaglin, 1993).
FATOR_MAD = 0.6745

# Regra 3: categorias em que várias notas iguais no mesmo dia são rotina:
# um bilhete por trecho/passageiro (ida e volta no mesmo dia têm o mesmo preço),
# pedágio de ida e volta, uma nota por diária de hotel, contas mensais e contratos fixos.
CATEGORIAS_REPETICAO_ROTINEIRA = frozenset(
    {
        "passagem-aerea-sigepa",
        "passagem-aerea-rpa",
        "passagem-aerea-reembolso",
        "passagem-aerea-missao-oficial",
        "passagens-terrestres-maritimas-ou-fluviais",
        "servico-de-taxi-pedagio-e-estacionamento",
        "hospedagem-exceto-do-parlamentar-no-distrito-federal",
        "telefonia",
        "complementacao-do-auxilio-moradia",
        "locacao-ou-fretamento-de-veiculos-automotores",
        "manutencao-de-escritorio-de-apoio-a-atividade-parlamentar",
    }
)

# Nome de cada regra para exibir (o mesmo usado na página de Metodologia)
NOMES_REGRAS = {
    "valor_atipico_categoria_uf": "Valor atípico para a categoria no estado",
    "concentracao_fornecedor": "Concentração em um fornecedor",
    "notas_repetidas": "Notas repetidas",
    "gasto_mensal_atipico": "Gasto mensal atípico",
}

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


@dataclass
class AlertaCalculado:
    """Um alerta pronto para gravar (espelha a tabela `alertas`)."""

    chave: str  # identificador estável: o mesmo achado gera sempre a mesma chave
    regra: str
    deputado_id: int
    categoria_id: int | None
    ano: int
    mes: int | None
    despesa_id: int | None
    score: float
    valor_referencia: float | None
    explicacao: str


# --------------------------------------------------------------- utilitários


def moeda(valor: float) -> str:
    """1234.5 -> 'R$ 1.234,50' (formato brasileiro, sem depender do locale do sistema)."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def vezes(razao: float) -> str:
    """4.234 -> '4,2'"""
    return f"{razao:.1f}".replace(".", ",")


def z_robusto(valores: np.ndarray) -> np.ndarray:
    """z-score robusto: 0,6745 * (x - mediana) / MAD.

    Por que não o z-score comum (média e desvio-padrão)? Porque os próprios
    valores extremos inflam a média e o desvio, e acabam "se escondendo".
    Mediana e MAD (desvio absoluto mediano) quase não se mexem com extremos.

    Se o MAD for zero (mais da metade dos valores idênticos), usa o desvio
    absoluto MÉDIO, como recomendam Iglewicz e Hoaglin. Se também for zero,
    todos os valores são iguais e ninguém é atípico (z = 0).
    """
    valores = np.asarray(valores, dtype=float)
    mediana = np.median(valores)
    desvios = np.abs(valores - mediana)
    mad = np.median(desvios)
    if mad > 0:
        return FATOR_MAD * (valores - mediana) / mad
    desvio_medio = np.mean(desvios)
    if desvio_medio > 0:
        return (valores - mediana) / (1.253314 * desvio_medio)
    return np.zeros_like(valores)


# ------------------------------------------------------------------ regras


def regra_valor_atipico_categoria_uf(df: pd.DataFrame, cfg: Settings) -> list[AlertaCalculado]:
    """Regra 1: nota com valor muito acima das notas da mesma categoria no mesmo estado.

    - Compara dentro de (categoria, UF), porque a cota varia por estado.
    - O z-score é calculado sobre o LOGARITMO do valor. Gastos têm distribuição
      muito assimétrica (muitas notas pequenas, poucas grandes); no valor bruto,
      quase toda nota grande viraria alerta (testamos: ~10 mil alertas contra
      ~1,9 mil no log). No log, "fora do padrão" passa a significar "muitas
      vezes maior que o típico", que é o que interessa.
    - Só grupos com pelo menos `anomalia_min_grupo` notas (estatística com
      poucas notas não é confiável).
    """
    positivas = df[df["valor"] > 0]
    alertas = []
    for (_, uf), grupo in positivas.groupby(["categoria_id", "uf"]):
        if len(grupo) < cfg.anomalia_min_grupo:
            continue
        z = z_robusto(np.log(grupo["valor"].to_numpy()))
        mediana = float(np.median(grupo["valor"]))
        for linha, score in zip(grupo.itertuples(), z, strict=True):
            if score <= cfg.anomalia_z_limiar:
                continue
            alertas.append(
                AlertaCalculado(
                    chave=f"valor_atipico_categoria_uf:despesa:{linha.id}",
                    regra="valor_atipico_categoria_uf",
                    deputado_id=int(linha.deputado_id),
                    categoria_id=int(linha.categoria_id),
                    ano=int(linha.ano),
                    mes=int(linha.mes),
                    despesa_id=int(linha.id),
                    score=round(float(score), 2),
                    valor_referencia=round(mediana, 2),
                    explicacao=(
                        f"Valor de {moeda(linha.valor)} é {vezes(linha.valor / mediana)} vezes a mediana de "
                        f"{linha.categoria_nome} para deputados de {uf} ({moeda(mediana)})."
                    ),
                )
            )
    return alertas


def regra_concentracao_fornecedor(df: pd.DataFrame, cfg: Settings) -> list[AlertaCalculado]:
    """Regra 2: um único fornecedor recebe mais de X% do gasto do deputado numa categoria no ano.

    Só vale para categorias em que concentrar é INCOMUM. Em várias categorias,
    um fornecedor só é o normal (a companhia telefônica, o aluguel do escritório,
    o contrato de locação do carro). Em vez de uma lista fixa, o critério vem dos
    dados: a regra só se aplica às categorias em que a MEDIANA da fatia do maior
    fornecedor (entre os deputados) fica abaixo do limite. Ou seja, onde o
    deputado típico divide os gastos entre vários fornecedores.
    """
    base = df[(df["valor"] > 0) & df["fornecedor_id"].notna()]
    chave_grupo = ["deputado_id", "categoria_id", "ano"]
    por_fornecedor = (
        base.groupby([*chave_grupo, "fornecedor_id"])
        .agg(
            valor=("valor", "sum"),
            notas=("id", "size"),
            fornecedor_nome=("fornecedor_nome", "first"),
            categoria_nome=("categoria_nome", "first"),
        )
        .reset_index()
    )
    por_fornecedor["total"] = por_fornecedor.groupby(chave_grupo)["valor"].transform("sum")
    por_fornecedor["notas_total"] = por_fornecedor.groupby(chave_grupo)["notas"].transform("sum")
    por_fornecedor["fatia"] = por_fornecedor["valor"] / por_fornecedor["total"]

    # Maior fornecedor de cada (deputado, categoria, ano) com volume suficiente
    maiores = por_fornecedor.sort_values("fatia").groupby(chave_grupo).tail(1)
    maiores = maiores[
        (maiores["total"] >= cfg.anomalia_concentracao_min_total)
        & (maiores["notas_total"] >= cfg.anomalia_concentracao_min_notas)
    ]
    # Critério tirado dos dados: categorias onde concentrar é o normal ficam de fora
    mediana_por_categoria = maiores.groupby("categoria_id")["fatia"].median()
    elegiveis = set(mediana_por_categoria[mediana_por_categoria < cfg.anomalia_concentracao_limite].index)

    alertas = []
    for linha in maiores.itertuples():
        if linha.categoria_id not in elegiveis or linha.fatia <= cfg.anomalia_concentracao_limite:
            continue
        tipico = mediana_por_categoria[linha.categoria_id]
        alertas.append(
            AlertaCalculado(
                chave=f"concentracao_fornecedor:{linha.deputado_id}:{linha.categoria_id}:{linha.ano}:{int(linha.fornecedor_id)}",
                regra="concentracao_fornecedor",
                deputado_id=int(linha.deputado_id),
                categoria_id=int(linha.categoria_id),
                ano=int(linha.ano),
                mes=None,  # alerta do ano inteiro
                despesa_id=None,
                score=round(float(linha.fatia) * 100, 1),  # % do maior fornecedor
                valor_referencia=round(float(linha.total), 2),
                explicacao=(
                    f"O fornecedor {linha.fornecedor_nome} recebeu {round(linha.fatia * 100)}% do gasto com "
                    f"{linha.categoria_nome} em {linha.ano} ({moeda(linha.valor)} de {moeda(linha.total)}). "
                    f"Nesta categoria, o maior fornecedor de um deputado costuma ficar com {round(tipico * 100)}%."
                ),
            )
        )
    return alertas


def regra_notas_repetidas(df: pd.DataFrame, cfg: Settings) -> list[AlertaCalculado]:
    """Regra 3: duas ou mais notas do mesmo fornecedor, com o mesmo valor, na mesma data
    (ou com até `anomalia_repetidas_janela_dias` dias de diferença).

    Fica de fora: notas pequenas e as categorias em que repetir é rotina
    (CATEGORIAS_REPETICAO_ROTINEIRA).
    """
    base = df[
        (df["valor"] >= cfg.anomalia_repetidas_valor_minimo)
        & df["fornecedor_id"].notna()
        & df["data_documento"].notna()
        & ~df["categoria_slug"].isin(CATEGORIAS_REPETICAO_ROTINEIRA)
    ].copy()
    if base.empty:
        return []
    base["data_documento"] = pd.to_datetime(base["data_documento"])
    base = base.sort_values(["deputado_id", "fornecedor_id", "valor", "data_documento", "id"])

    # Agrupa notas "em sequência": mesmo deputado+fornecedor+valor e diferença de
    # datas dentro da janela. Cada vez que a diferença estoura a janela, começa um grupo novo.
    mesma_chave = ["deputado_id", "fornecedor_id", "valor"]
    dias = base.groupby(mesma_chave)["data_documento"].diff().dt.days
    base["grupo"] = (dias.isna() | (dias > cfg.anomalia_repetidas_janela_dias)).cumsum()

    alertas = []
    for _, grupo in base.groupby("grupo"):
        if len(grupo) < 2:
            continue
        primeira = grupo.iloc[0]
        data_inicial: date = primeira["data_documento"].date()
        data_txt = data_inicial.strftime("%d/%m/%Y")
        quando = (
            f"na mesma data ({data_txt})"
            if grupo["data_documento"].nunique() == 1
            else f"em datas próximas (a partir de {data_txt})"
        )
        alertas.append(
            AlertaCalculado(
                chave=(
                    f"notas_repetidas:{int(primeira['deputado_id'])}:{int(primeira['fornecedor_id'])}:"
                    f"{primeira['valor']:.2f}:{data_inicial.isoformat()}"
                ),
                regra="notas_repetidas",
                deputado_id=int(primeira["deputado_id"]),
                categoria_id=int(primeira["categoria_id"]),
                ano=int(primeira["ano"]),
                mes=int(primeira["mes"]),
                despesa_id=int(primeira["id"]),
                score=float(len(grupo)),  # quantas notas iguais
                valor_referencia=round(float(primeira["valor"]), 2),
                explicacao=(
                    f"{len(grupo)} notas de {moeda(primeira['valor'])} do mesmo fornecedor "
                    f"({primeira['fornecedor_nome']}) {quando}, em {primeira['categoria_nome']}."
                ),
            )
        )
    return alertas


def regra_gasto_mensal_atipico(df: pd.DataFrame, cfg: Settings) -> list[AlertaCalculado]:
    """Regra 4: total do deputado no mês muito acima do dos deputados do mesmo estado no mesmo mês.

    Dupla condição: z-score robusto acima do limiar E pelo menos N vezes a
    mediana. A segunda evita marcar diferenças pequenas em meses em que os
    deputados de um estado gastaram valores muito parecidos (MAD pequeno).

    Só entram meses CONSOLIDADOS. As notas chegam com até 90 dias de atraso:
    num mês recente, a maioria dos deputados ainda tem pouco lançado, a mediana
    fica artificialmente baixa e qualquer gasto normal pareceria "200 vezes a
    mediana". Critério tirado dos dados: o mês precisa ter pelo menos 60% do
    número típico (mediano) de notas por mês.
    """
    notas_por_mes = df.groupby(["ano", "mes"]).size()
    tipico = notas_por_mes.median() if len(notas_por_mes) else 0
    consolidados = set(notas_por_mes[notas_por_mes >= cfg.anomalia_mensal_completude_minima * tipico].index)

    totais = df.groupby(["deputado_id", "uf", "ano", "mes"])["valor"].sum().reset_index()
    alertas = []
    for (uf, ano, mes), grupo in totais.groupby(["uf", "ano", "mes"]):
        if (ano, mes) not in consolidados or len(grupo) < cfg.anomalia_mensal_min_deputados:
            continue
        valores = grupo["valor"].to_numpy()
        mediana = float(np.median(valores))
        if mediana <= 0:
            continue
        for linha, score in zip(grupo.itertuples(), z_robusto(valores), strict=True):
            razao = linha.valor / mediana
            if score <= cfg.anomalia_z_limiar or razao < cfg.anomalia_mensal_razao_minima:
                continue
            alertas.append(
                AlertaCalculado(
                    chave=f"gasto_mensal_atipico:{linha.deputado_id}:{ano}:{mes}",
                    regra="gasto_mensal_atipico",
                    deputado_id=int(linha.deputado_id),
                    categoria_id=None,
                    ano=int(ano),
                    mes=int(mes),
                    despesa_id=None,
                    score=round(float(score), 2),
                    valor_referencia=round(mediana, 2),
                    explicacao=(
                        f"O gasto total em {MESES[mes - 1]}/{ano} ({moeda(linha.valor)}) foi {vezes(razao)} vezes "
                        f"a mediana dos {len(grupo)} deputados de {uf} no mesmo mês ({moeda(mediana)})."
                    ),
                )
            )
    return alertas


REGRAS = (
    regra_valor_atipico_categoria_uf,
    regra_concentracao_fornecedor,
    regra_notas_repetidas,
    regra_gasto_mensal_atipico,
)


def calcular_alertas(df: pd.DataFrame, cfg: Settings) -> list[AlertaCalculado]:
    """Aplica as quatro regras. Se duas regras gerarem a mesma chave, fica a primeira."""
    vistos: dict[str, AlertaCalculado] = {}
    for regra in REGRAS:
        for alerta in regra(df, cfg):
            vistos.setdefault(alerta.chave, alerta)
    return list(vistos.values())
