"""DADOS DE EXEMPLO, SÓ PARA TESTES. Não representam despesas reais.

O formato imita exatamente o JSON da API da Câmara (conferido em nov/2026),
inclusive as peculiaridades: líquido com sinal invertido, glosa nula e
codDocumento em formato GUID.
"""

ID_DEPUTADO_TESTE = 999_000_001


def despesa_api(**sobrescrever) -> dict:
    base = {
        "ano": 2026,
        "mes": 9,
        "tipoDespesa": "COMBUSTÍVEIS E LUBRIFICANTES.",
        "codDocumento": "1000001",
        "tipoDocumento": "Nota Fiscal",
        "codTipoDocumento": 0,
        "dataDocumento": "2026-09-19T19:00:50",
        "numDocumento": "123",
        "valorDocumento": 300.0,
        "urlDocumento": "http://exemplo.invalido/nota/1000001",
        "nomeFornecedor": "POSTO EXEMPLO LTDA (TESTE)",
        "cnpjCpfFornecedor": "00.000.000/0001-91",
        "valorLiquido": -300.0,  # sinal invertido, como a API real faz
        "valorGlosa": 0.0,
        "numRessarcimento": "",
        "codLote": 1,
        "parcela": 0,
    }
    return {**base, **sobrescrever}


def deputado_api(**sobrescrever) -> dict:
    base = {
        "id": ID_DEPUTADO_TESTE,
        "nome": "Deputado de Teste",
        "siglaPartido": "TESTE",
        "siglaUf": "DF",
        "idLegislatura": 57,
        "urlFoto": None,
        "email": "teste@exemplo.invalido",
    }
    return {**base, **sobrescrever}
