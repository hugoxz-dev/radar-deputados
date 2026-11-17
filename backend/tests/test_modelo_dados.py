"""Testes do modelo de dados: as migrações criaram tudo e o banco protege as regras.

Estes testes mostram que as regras importantes não dependem só do código
Python: o próprio PostgreSQL recusa dados inválidos (CHECK, UNIQUE, FK).
"""

from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import Base, engine
from app.models import Categoria, Deputado, Despesa, Usuario

TABELAS_ESPERADAS = {
    "deputados",
    "fornecedores",
    "categorias",
    "despesas",
    "alertas",
    "resumos_ia",
    "usuarios",
    "assinaturas",
    "inscricoes_alerta",
    "execucoes_etl",
}


def test_migracoes_criaram_todas_as_tabelas():
    tabelas_no_banco = set(inspect(engine).get_table_names())
    assert tabelas_no_banco >= TABELAS_ESPERADAS
    # E os modelos Python declaram exatamente essas tabelas
    assert set(Base.metadata.tables) == TABELAS_ESPERADAS


def test_indices_dos_filtros_existem():
    insp = inspect(engine)
    indices_despesas = {i["name"] for i in insp.get_indexes("despesas")}
    assert {"ix_despesas_deputado_ano_mes", "ix_despesas_ano_mes", "ix_despesas_categoria_id"} <= indices_despesas
    assert "ix_deputados_uf" in {i["name"] for i in insp.get_indexes("deputados")}


def test_plano_invalido_e_recusado_pelo_banco(db):
    db.add(Usuario(email="teste@exemplo.com", senha_hash="x", nome="Teste", plano="premium"))
    with pytest.raises(IntegrityError, match="ck_usuarios_plano"):
        db.flush()


def test_email_de_usuario_e_unico(db):
    db.add(Usuario(email="repetido@exemplo.com", senha_hash="x", nome="A"))
    db.flush()
    db.add(Usuario(email="repetido@exemplo.com", senha_hash="y", nome="B"))
    with pytest.raises(IntegrityError, match="uq_usuarios_email"):
        db.flush()


def _despesa_de_teste(deputado_id: int, categoria_id: int, hash_unico: str) -> Despesa:
    return Despesa(
        deputado_id=deputado_id,
        categoria_id=categoria_id,
        ano=2026,
        mes=10,
        valor_documento=Decimal("100.00"),
        valor_liquido=Decimal("100.00"),
        hash_unico=hash_unico,
    )


def test_hash_unico_impede_despesa_duplicada(db):
    # Dados fictícios de teste (desfeitos pelo rollback da fixture)
    db.add(Deputado(id=999_999_001, nome="Deputado Teste", partido="TESTE", uf="DF", legislatura=57))
    categoria = Categoria(descricao="CATEGORIA DE TESTE", slug="categoria-de-teste")
    db.add(categoria)
    db.flush()

    db.add(_despesa_de_teste(999_999_001, categoria.id, "hash-igual"))
    db.flush()
    db.add(_despesa_de_teste(999_999_001, categoria.id, "hash-igual"))
    with pytest.raises(IntegrityError, match="uq_despesas_hash_unico"):
        db.flush()


def test_despesa_exige_deputado_existente(db):
    categoria = Categoria(descricao="OUTRA CATEGORIA DE TESTE", slug="outra-categoria-de-teste")
    db.add(categoria)
    db.flush()
    db.add(_despesa_de_teste(123_456_789, categoria.id, "hash-orfa"))  # deputado inexistente
    with pytest.raises(IntegrityError, match="fk_despesas_deputado_id_deputados"):
        db.flush()
