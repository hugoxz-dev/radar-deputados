"""Testes da API pública com DADOS FICTÍCIOS numa UF inexistente ("ZZ").

Usar uma UF que não existe isola os testes dos dados reais carregados pelo
ETL: os filtros por uf=ZZ só enxergam o que o teste criou (e o rollback
da fixture apaga tudo no fim).
"""

from decimal import Decimal

import pytest

from app.models import Categoria, Deputado, Despesa
from app.services.periodo import Periodo

UF = "ZZ"


@pytest.fixture
def cenario(db):
    """3 deputados fictícios em ZZ, com totais 100, 300 e 1000 em out/2026."""
    cat_a = Categoria(descricao="CATEGORIA TESTE A", slug="categoria-teste-a")
    cat_b = Categoria(descricao="CATEGORIA TESTE B", slug="categoria-teste-b")
    db.add_all([cat_a, cat_b])
    deputados = [
        Deputado(
            id=990_001, nome="Joséfa Teste", nome_civil="JOSEFA DA SILVA TESTE", partido="PTESTE", uf=UF, legislatura=57
        ),
        Deputado(id=990_002, nome="Bruno Teste", partido="PTESTE", uf=UF, legislatura=57),
        Deputado(id=990_003, nome="Carla Teste", partido="OUTRO", uf=UF, legislatura=57, em_exercicio=False),
    ]
    db.add_all(deputados)
    db.flush()

    def nota(dep_id, cat, valor, n):
        return Despesa(
            deputado_id=dep_id,
            categoria_id=cat.id,
            ano=2026,
            mes=10,
            valor_documento=Decimal(valor),
            valor_liquido=Decimal(valor),
            hash_unico=f"teste-api-{dep_id}-{n}",
        )

    db.add_all(
        [
            nota(990_001, cat_a, "60.00", 1),
            nota(990_001, cat_b, "40.00", 2),  # total 100
            nota(990_002, cat_a, "300.00", 3),  # total 300
            nota(990_003, cat_a, "1000.00", 4),  # total 1000
        ]
    )
    db.flush()
    return {"cat_a": cat_a, "cat_b": cat_b}


PERIODO = "de=2026-10&ate=2026-10"


def test_busca_ignora_acento_e_maiusculas(cliente, cenario):
    r = cliente.get(f"/deputados?busca=JOSEFA&uf={UF}")
    assert [d["nome"] for d in r.json()["itens"]] == ["Joséfa Teste"]


def test_lista_ordenada_por_total_com_valores_numericos(cliente, cenario):
    r = cliente.get(f"/deputados?uf={UF}&ordenar=total&{PERIODO}")
    corpo = r.json()
    assert corpo["total"] == 3
    assert [d["total_periodo"] for d in corpo["itens"]] == [1000.0, 300.0, 100.0]  # números, não texto


def test_filtro_em_exercicio(cliente, cenario):
    r = cliente.get(f"/deputados?uf={UF}&em_exercicio=true")
    assert {d["nome"] for d in r.json()["itens"]} == {"Joséfa Teste", "Bruno Teste"}


def test_perfil_calcula_totais_e_mediana_da_uf(cliente, cenario):
    r = cliente.get(f"/deputados/990001?{PERIODO}")
    assert r.status_code == 200
    p = r.json()
    assert p["total"] == 100.0
    assert p["n_notas"] == 2
    assert [c["percentual"] for c in p["por_categoria"]] == [60.0, 40.0]
    # Mediana de (100, 300, 1000) = 300; o deputado gastou 1/3 da mediana
    assert p["comparacao_uf"] == {"uf": UF, "mediana_uf": 300.0, "n_deputados_uf": 3, "razao": 0.33}


def test_perfil_preenche_meses_sem_gasto(cliente, cenario):
    p = cliente.get("/deputados/990001?de=2026-09&ate=2026-11").json()
    assert [(m["mes"], m["total"]) for m in p["por_mes"]] == [(9, 0.0), (10, 100.0), (11, 0.0)]


def test_despesas_filtra_por_categoria(cliente, cenario):
    r = cliente.get(f"/deputados/990001/despesas?categoria=categoria-teste-b&{PERIODO}")
    itens = r.json()["itens"]
    assert len(itens) == 1
    assert itens[0]["valor_liquido"] == 40.0


def test_ranking_por_partido_com_media(cliente, cenario):
    r = cliente.get(f"/rankings?tipo=partido&uf={UF}&ordem=media&{PERIODO}")
    itens = r.json()["itens"]
    # OUTRO: 1000 / 1 deputado; PTESTE: 400 / 2 deputados = 200
    assert [(i["chave"], i["media_por_deputado"]) for i in itens] == [("OUTRO", 1000.0), ("PTESTE", 200.0)]


def test_ranking_de_deputados_por_categoria(cliente, cenario):
    r = cliente.get(f"/rankings?tipo=deputado&uf={UF}&categoria=categoria-teste-b&{PERIODO}")
    assert [i["nome"] for i in r.json()["itens"]] == ["Joséfa Teste"]


def test_erros_claros(cliente, cenario):
    assert cliente.get("/deputados/1").status_code == 404
    assert cliente.get("/deputados?de=2026-13").status_code == 422
    assert cliente.get("/deputados?de=2026-10&ate=2026-01").status_code == 422
    assert cliente.get("/rankings?tipo=inexistente").status_code == 422


def test_periodo_lista_meses_atravessando_o_ano():
    assert Periodo(de=(2025, 11), ate=(2026, 2)).meses() == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
