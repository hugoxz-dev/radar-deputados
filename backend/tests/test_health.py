"""Teste de fumaça: a API sobe e o /health responde.

Usa o TestClient do FastAPI, que chama a API sem precisar de servidor rodando.
Precisa do banco no ar (docker compose up db).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde_ok_com_banco_no_ar():
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["banco"] == "ok"
