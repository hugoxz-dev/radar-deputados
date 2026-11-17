"""Fixtures compartilhadas pelos testes.

A fixture `db` abre uma transação e desfaz tudo no fim de cada teste
(rollback). Assim os testes podem inserir à vontade sem sujar o banco
de desenvolvimento e sem depender da ordem em que rodam.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def db() -> Iterator[Session]:
    conexao = engine.connect()
    transacao = conexao.begin()
    # create_savepoint: um session.commit() dentro do teste vira um SAVEPOINT,
    # e a transação externa continua aberta para o rollback final.
    sessao = Session(bind=conexao, join_transaction_mode="create_savepoint")
    try:
        yield sessao
    finally:
        sessao.close()
        transacao.rollback()
        conexao.close()


@pytest.fixture
def cliente(db: Session) -> Iterator[TestClient]:
    """Cliente HTTP da API que usa a MESMA sessão do teste.

    Assim a API enxerga os dados que o teste inseriu, e tudo é desfeito no fim.
    `dependency_overrides` é o jeito do FastAPI de trocar uma dependência em testes.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
