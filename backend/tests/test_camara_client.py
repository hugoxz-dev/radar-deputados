"""Testes do cliente da API da Câmara com uma API SIMULADA (httpx.MockTransport).

Não acessam a internet: testam paginação, retry e tratamento de erro de forma
rápida e repetível.
"""

import httpx
import pytest

from app.services.camara_client import CamaraClient, ErroApiCamara


def cliente_com(handler) -> CamaraClient:
    return CamaraClient(
        base_url="https://api.simulada",
        pausa_segundos=0,
        max_tentativas=3,
        transport=httpx.MockTransport(handler),
    )


def test_paginacao_segue_ate_nao_haver_link_next():
    paginas_pedidas = []

    def handler(request: httpx.Request) -> httpx.Response:
        pagina = int(request.url.params["pagina"])
        paginas_pedidas.append(pagina)
        links = [{"rel": "next", "href": "..."}] if pagina < 3 else []
        return httpx.Response(200, json={"dados": [{"id": pagina}], "links": links})

    with cliente_com(handler) as cliente:
        deputados = cliente.listar_deputados()
    assert [d["id"] for d in deputados] == [1, 2, 3]
    assert paginas_pedidas == [1, 2, 3]


def test_meses_vao_como_parametro_repetido():
    recebidos = []

    def handler(request: httpx.Request) -> httpx.Response:
        recebidos.append(request.url.params.get_list("mes"))
        return httpx.Response(200, json={"dados": [], "links": []})

    with cliente_com(handler) as cliente:
        cliente.listar_despesas(1, 2025, [11, 12])
    assert recebidos == [["11", "12"]]


def test_retry_em_erro_temporario(monkeypatch):
    monkeypatch.setattr("app.services.camara_client.time.sleep", lambda _: None)  # não esperar de verdade
    tentativas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas["n"] += 1
        if tentativas["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"dados": [{"id": 57}], "links": []})

    with cliente_com(handler) as cliente:
        assert cliente.legislatura_atual() == 57
    assert tentativas["n"] == 3


def test_desiste_depois_do_maximo_de_tentativas(monkeypatch):
    monkeypatch.setattr("app.services.camara_client.time.sleep", lambda _: None)
    with cliente_com(lambda r: httpx.Response(500)) as cliente, pytest.raises(ErroApiCamara):
        cliente.legislatura_atual()


def test_404_falha_sem_tentar_de_novo():
    tentativas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas["n"] += 1
        return httpx.Response(404)

    with cliente_com(handler) as cliente, pytest.raises(ErroApiCamara):
        cliente.detalhar_deputado(123)
    assert tentativas["n"] == 1
