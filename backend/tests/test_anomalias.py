"""Testes das 4 regras de gasto fora do padrão com DADOS FICTÍCIOS (só para teste).

As regras são funções puras sobre DataFrames: cada teste monta o cenário
mínimo que deve (ou não) gerar alerta. Nenhum acesso a banco.
"""

from datetime import date
from itertools import count

import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.services.anomalias import (
    calcular_alertas,
    moeda,
    regra_concentracao_fornecedor,
    regra_gasto_mensal_atipico,
    regra_notas_repetidas,
    regra_valor_atipico_categoria_uf,
    z_robusto,
)

CFG = Settings()  # parâmetros padrão (os mesmos do .env.example)
_ids = count(1)

# Palavras proibidas em qualquer texto gerado (regra de linguagem do projeto)
PROIBIDAS = ("suspeit", "irregular", "fraude", "desvio")


def nota(
    deputado=1,
    uf="MA",
    categoria=1,
    slug="combustiveis-e-lubrificantes",
    nome_cat="Combustíveis e lubrificantes",
    fornecedor=10,
    nome_forn="POSTO TESTE",
    ano=2026,
    mes=3,
    dia=10,
    valor=100.0,
) -> dict:
    return {
        "id": next(_ids),
        "deputado_id": deputado,
        "uf": uf,
        "categoria_id": categoria,
        "categoria_slug": slug,
        "categoria_nome": nome_cat,
        "fornecedor_id": fornecedor,
        "fornecedor_nome": nome_forn,
        "ano": ano,
        "mes": mes,
        "data_documento": date(ano, mes, dia),
        "valor": valor,
    }


def df(*linhas: dict) -> pd.DataFrame:
    return pd.DataFrame(list(linhas))


def checar_linguagem(alertas):
    for a in alertas:
        assert not any(p in a.explicacao.lower() for p in PROIBIDAS), a.explicacao


# ------------------------------------------------------------ z robusto


def test_z_robusto_ignora_o_proprio_extremo():
    valores = np.array([10, 11, 9, 10, 12, 10, 1000.0])
    z = z_robusto(valores)
    assert z[-1] > 100  # o extremo fica muito acima
    assert abs(z[0]) < 1  # os normais ficam perto de zero


def test_z_robusto_com_mad_zero_usa_desvio_medio():
    # Mais da metade igual a 100 -> MAD = 0; não pode dividir por zero
    z = z_robusto(np.array([100, 100, 100, 100, 500.0]))
    assert np.isfinite(z).all() and z[-1] > 0


def test_z_robusto_todos_iguais_da_zero():
    assert (z_robusto(np.array([5.0, 5.0, 5.0])) == 0).all()


# ---------------------------------------------- regra 1: valor atípico


def test_regra1_marca_nota_muito_acima_da_mediana_da_uf():
    normais = [nota(valor=200 + i % 20, dia=1 + i % 28) for i in range(40)]
    extrema = nota(valor=5000, deputado=2)
    alertas = regra_valor_atipico_categoria_uf(df(*normais, extrema), CFG)
    assert [a.despesa_id for a in alertas] == [extrema["id"]]
    assert "vezes a mediana de Combustíveis e lubrificantes para deputados de MA" in alertas[0].explicacao
    checar_linguagem(alertas)


def test_regra1_compara_so_dentro_da_mesma_uf():
    # Em RR as notas são todas altas: 5000 é normal lá, mesmo sendo alto em MA
    ma = [nota(uf="MA", valor=200 + i % 20) for i in range(40)]
    rr = [nota(uf="RR", deputado=3, valor=4900 + i % 200) for i in range(40)]
    assert regra_valor_atipico_categoria_uf(df(*ma, *rr), CFG) == []


def test_regra1_ignora_grupos_pequenos():
    poucas = [nota(valor=200) for _ in range(5)] + [nota(valor=99999)]
    assert regra_valor_atipico_categoria_uf(df(*poucas), CFG) == []


# ----------------------------------------- regra 2: concentração


def _deputado_dividido(deputado: int, categoria=1, slug="combustiveis-e-lubrificantes"):
    """Deputado 'típico': 10 notas em 5 fornecedores diferentes (20% cada)."""
    return [
        nota(deputado=deputado, categoria=categoria, slug=slug, fornecedor=100 + i % 5, valor=2000) for i in range(10)
    ]


def test_regra2_marca_fornecedor_dominante_em_categoria_normalmente_pulverizada():
    tipicos = [n for d in range(1, 6) for n in _deputado_dividido(d)]
    concentrado = [nota(deputado=9, fornecedor=777, nome_forn="POSTO UNICO", valor=2000) for _ in range(8)]
    concentrado += [nota(deputado=9, fornecedor=778, valor=2000) for _ in range(2)]  # 80% num só
    alertas = regra_concentracao_fornecedor(df(*tipicos, *concentrado), CFG)
    assert [(a.deputado_id, a.score) for a in alertas] == [(9, 80.0)]
    assert "POSTO UNICO recebeu 80%" in alertas[0].explicacao
    assert "costuma ficar com 20%" in alertas[0].explicacao
    assert alertas[0].mes is None  # alerta anual
    checar_linguagem(alertas)


def test_regra2_nao_se_aplica_onde_concentrar_e_o_normal():
    # Telefonia: todo deputado usa uma operadora só -> mediana da fatia = 100% -> categoria fora
    todos_concentrados = [
        nota(deputado=d, categoria=2, slug="telefonia", fornecedor=50, valor=2500)
        for d in range(1, 6)
        for _ in range(5)
    ]
    assert regra_concentracao_fornecedor(df(*todos_concentrados), CFG) == []


def test_regra2_ignora_gasto_pequeno():
    tipicos = [n for d in range(1, 6) for n in _deputado_dividido(d)]
    pequeno = [nota(deputado=9, fornecedor=777, valor=100) for _ in range(6)]  # R$ 600 < R$ 10 mil
    assert regra_concentracao_fornecedor(df(*tipicos, *pequeno), CFG) == []


# ------------------------------------------- regra 3: notas repetidas


def test_regra3_marca_notas_iguais_no_mesmo_dia():
    a = nota(slug="divulgacao-da-atividade-parlamentar", nome_cat="Divulgação", valor=7665, dia=25)
    b = nota(slug="divulgacao-da-atividade-parlamentar", nome_cat="Divulgação", valor=7665, dia=25)
    alertas = regra_notas_repetidas(df(a, b), CFG)
    assert len(alertas) == 1
    assert alertas[0].score == 2
    assert alertas[0].despesa_id == a["id"]
    assert (
        "2 notas de R$ 7.665,00 do mesmo fornecedor (POSTO TESTE) na mesma data (25/03/2026)" in alertas[0].explicacao
    )
    checar_linguagem(alertas)


def test_regra3_dias_diferentes_nao_repetem_com_janela_zero():
    assert regra_notas_repetidas(df(nota(valor=300, dia=1), nota(valor=300, dia=2)), CFG) == []


def test_regra3_janela_configuravel():
    cfg = Settings(anomalia_repetidas_janela_dias=3)
    alertas = regra_notas_repetidas(df(nota(valor=300, dia=1), nota(valor=300, dia=3)), cfg)
    assert len(alertas) == 1 and "datas próximas" in alertas[0].explicacao


def test_regra3_ignora_categorias_de_repeticao_rotineira_e_valores_pequenos():
    pedagio = [nota(slug="servico-de-taxi-pedagio-e-estacionamento", valor=500) for _ in range(2)]
    pequenas = [nota(valor=50) for _ in range(2)]
    assert regra_notas_repetidas(df(*pedagio, *pequenas), CFG) == []


# ---------------------------------------- regra 4: gasto mensal atípico


def test_regra4_marca_mes_muito_acima_dos_colegas_da_uf():
    colegas = [nota(deputado=d, valor=20000 + d * 500) for d in range(1, 9)]
    fora = nota(deputado=99, valor=90000)
    alertas = regra_gasto_mensal_atipico(df(*colegas, fora), CFG)
    assert [a.deputado_id for a in alertas] == [99]
    assert "O gasto total em mar/2026 (R$ 90.000,00) foi" in alertas[0].explicacao
    assert "dos 9 deputados de MA" in alertas[0].explicacao
    checar_linguagem(alertas)


def test_regra4_exige_dobro_da_mediana():
    # z alto (colegas muito parecidos) mas só 1,5x a mediana: não marca
    colegas = [nota(deputado=d, valor=20000 + d) for d in range(1, 9)]
    assert regra_gasto_mensal_atipico(df(*colegas, nota(deputado=99, valor=30000)), CFG) == []


def test_regra4_ignora_mes_ainda_incompleto():
    """Mês com poucas notas lançadas (atraso) não é comparado: a mediana estaria artificialmente baixa."""
    meses_cheios = [nota(deputado=d, mes=m, valor=20000) for m in (1, 2, 3) for d in range(1, 10) for _ in range(3)]
    # Abril: só 9 notas (contra 27 nos outros meses), com um deputado "muito acima"
    abril = [nota(deputado=d, mes=4, valor=300) for d in range(1, 9)] + [nota(deputado=99, mes=4, valor=20000)]
    alertas = regra_gasto_mensal_atipico(df(*meses_cheios, *abril), CFG)
    assert [a for a in alertas if a.mes == 4] == []


# ------------------------------------------------------------- geral


def test_calcular_alertas_gera_chaves_estaveis():
    normais = [nota(valor=200 + i % 20) for i in range(40)]
    dados = df(*normais, nota(valor=5000, deputado=2))
    primeira = sorted(a.chave for a in calcular_alertas(dados, CFG))
    segunda = sorted(a.chave for a in calcular_alertas(dados, CFG))
    assert primeira == segunda and primeira


@pytest.mark.parametrize("valor,esperado", [(1234.5, "R$ 1.234,50"), (0.1, "R$ 0,10"), (1000000, "R$ 1.000.000,00")])
def test_moeda_formato_brasileiro(valor, esperado):
    assert moeda(valor) == esperado
