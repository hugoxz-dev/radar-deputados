"""Testes da etapa de transformação (funções puras, sem rede nem banco)."""

from datetime import date
from decimal import Decimal

from app.etl.extrair import agrupar_por_ano, periodos_ultimos_meses
from app.etl.transformar import para_decimal, slugify, so_digitos, transformar_despesas
from tests.dados_exemplo import ID_DEPUTADO_TESTE, despesa_api


def test_valor_liquido_corrige_sinal_invertido_da_api():
    [linha] = transformar_despesas([despesa_api(valorDocumento=300.0, valorLiquido=-300.0)], ID_DEPUTADO_TESTE)
    assert linha["valor_liquido"] == Decimal("300.00")


def test_valor_liquido_desconta_glosa():
    [linha] = transformar_despesas(
        [despesa_api(valorDocumento=500.0, valorGlosa=120.5, valorLiquido=-379.5)], ID_DEPUTADO_TESTE
    )
    assert linha["valor_liquido"] == Decimal("379.50")


def test_credito_de_passagem_cancelada_continua_negativo():
    [linha] = transformar_despesas([despesa_api(valorDocumento=-921.9, valorLiquido=-921.9)], ID_DEPUTADO_TESTE)
    assert linha["valor_liquido"] == Decimal("-921.90")


def test_glosa_nula_vira_zero():
    [linha] = transformar_despesas([despesa_api(valorGlosa=None)], ID_DEPUTADO_TESTE)
    assert linha["valor_glosa"] == Decimal("0.00")


def test_cod_documento_guid_e_aceito():
    guid = "D09DD946-9453-4CE1-9FE5-FB6422250F98"
    [linha] = transformar_despesas([despesa_api(codDocumento=guid)], ID_DEPUTADO_TESTE)
    assert linha["cod_documento"] == guid


def test_data_com_hora_e_data_nula():
    linhas = transformar_despesas([despesa_api(), despesa_api(dataDocumento=None, codDocumento="2")], ID_DEPUTADO_TESTE)
    assert linhas[0]["data_documento"] == date(2026, 9, 19)
    assert linhas[1]["data_documento"] is None


def test_hash_e_estavel_entre_execucoes():
    a = transformar_despesas([despesa_api()], ID_DEPUTADO_TESTE)
    b = transformar_despesas([despesa_api()], ID_DEPUTADO_TESTE)
    assert a[0]["hash_unico"] == b[0]["hash_unico"]


def test_hash_ignora_campos_que_a_camara_corrige():
    """Mudou a glosa? É a MESMA nota (vai ser atualizada, não duplicada)."""
    antes = transformar_despesas([despesa_api(valorGlosa=0.0)], ID_DEPUTADO_TESTE)
    depois = transformar_despesas([despesa_api(valorGlosa=50.0)], ID_DEPUTADO_TESTE)
    assert antes[0]["hash_unico"] == depois[0]["hash_unico"]


def test_notas_identicas_recebem_hashes_diferentes():
    """Duas contas iguais no mesmo mês são duas notas, não uma duplicata."""
    linhas = transformar_despesas([despesa_api(), despesa_api()], ID_DEPUTADO_TESTE)
    assert linhas[0]["hash_unico"] != linhas[1]["hash_unico"]


def test_auxiliares():
    assert slugify("COMBUSTÍVEIS E LUBRIFICANTES.") == "combustiveis-e-lubrificantes"
    assert slugify("HOSPEDAGEM ,EXCETO DO PARLAMENTAR NO DISTRITO FEDERAL.") == (
        "hospedagem-exceto-do-parlamentar-no-distrito-federal"
    )
    assert so_digitos("00.000.000/0001-91") == "00000000000191"
    assert para_decimal(0.1) + para_decimal(0.2) == Decimal("0.30")  # sem erro de float


def test_periodos_atravessam_virada_de_ano():
    assert periodos_ultimos_meses(3, date(2026, 2, 10)) == [(2025, 12), (2026, 1), (2026, 2)]
    assert len(periodos_ultimos_meses(12, date(2026, 11, 13))) == 12
    assert agrupar_por_ano([(2025, 12), (2026, 1), (2026, 2)]) == {2025: [12], 2026: [1, 2]}
