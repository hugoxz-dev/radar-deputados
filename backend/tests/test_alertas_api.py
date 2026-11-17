"""Testes da gravação de alertas (sincronização) e das rotas /alertas.

Dados FICTÍCIOS numa UF inexistente (ZZ), desfeitos pelo rollback da fixture.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.etl.carregar import gravar_alertas
from app.models import Alerta, Categoria, Deputado, Despesa
from app.services.anomalias import AlertaCalculado

UF = "ZZ"


@pytest.fixture
def base(db):
    cat = Categoria(descricao="CATEGORIA TESTE ALERTA", slug="categoria-teste-alerta")
    db.add_all([cat, Deputado(id=991_001, nome="Deputada Alerta Teste", partido="PTESTE", uf=UF, legislatura=57)])
    db.flush()
    nota = Despesa(
        deputado_id=991_001,
        categoria_id=cat.id,
        ano=2026,
        mes=5,
        valor_documento=Decimal("900"),
        valor_liquido=Decimal("900"),
        hash_unico="teste-alerta-1",
    )
    db.add(nota)
    db.flush()
    return {"cat": cat, "nota": nota}


def alerta(chave: str, base, **extra) -> AlertaCalculado:
    dados = dict(
        chave=chave,
        regra="valor_atipico_categoria_uf",
        deputado_id=991_001,
        categoria_id=base["cat"].id,
        ano=2026,
        mes=5,
        despesa_id=base["nota"].id,
        score=5.0,
        valor_referencia=100.0,
        explicacao="Valor de teste é 9 vezes a mediana.",
    )
    return AlertaCalculado(**{**dados, **extra})


def _chaves(db):
    return set(db.scalars(select(Alerta.chave).where(Alerta.deputado_id == 991_001)))


def test_gravar_alertas_identifica_novos_e_nao_duplica(db, base):
    novos, _ = gravar_alertas(db, [alerta("teste:a", base)])
    assert len(novos) == 1
    novos, _ = gravar_alertas(db, [alerta("teste:a", base, score=7.0)])  # recálculo
    assert novos == []  # mesmo achado: não é novo
    assert db.scalar(select(Alerta.score).where(Alerta.chave == "teste:a")) == 7.0  # mas foi atualizado


def test_gravar_alertas_remove_os_que_nao_se_aplicam_mais(db, base):
    gravar_alertas(db, [alerta("teste:a", base), alerta("teste:b", base)])
    _, removidos = gravar_alertas(db, [alerta("teste:a", base)])
    assert removidos >= 1
    assert _chaves(db) == {"teste:a"}


def test_feed_filtra_por_uf_e_traz_nota(cliente, db, base):
    gravar_alertas(db, [alerta("teste:a", base)])
    r = cliente.get(f"/alertas?uf={UF}&de=2026-01&ate=2026-12")
    corpo = r.json()
    assert corpo["total"] == 1
    item = corpo["itens"][0]
    assert item["regra_nome"] == "Valor atípico para a categoria no estado"
    assert item["deputado"]["nome"] == "Deputada Alerta Teste"
    assert item["nota"]["valor_liquido"] == 900.0


def test_alerta_anual_aparece_quando_o_ano_se_sobrepoe_ao_periodo(cliente, db, base):
    """Concentração é anual (mes nulo): um alerta de 2026 deve aparecer em dez/2025 a nov/2026."""
    gravar_alertas(db, [alerta("teste:anual", base, regra="concentracao_fornecedor", mes=None, despesa_id=None)])
    r = cliente.get(f"/alertas?uf={UF}&de=2025-12&ate=2026-11")
    assert [i["regra"] for i in r.json()["itens"]] == ["concentracao_fornecedor"]
    # Período só em 2025 (dentro da janela pública): o alerta anual de 2026 não aparece
    assert cliente.get(f"/alertas?uf={UF}&de=2025-12&ate=2025-12").json()["total"] == 0


def test_alertas_do_deputado_e_404(cliente, db, base):
    gravar_alertas(db, [alerta("teste:a", base)])
    assert cliente.get("/deputados/991001/alertas?de=2026-01&ate=2026-12").json()["total"] == 1
    assert cliente.get("/deputados/1/alertas").status_code == 404
