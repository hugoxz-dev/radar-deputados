"""Cliente HTTP da API de Dados Abertos da Câmara dos Deputados.

Documentação oficial: https://dadosabertos.camara.leg.br/swagger/api.html

O que foi conferido na API real antes de escrever este código (nov/2026):
- Toda resposta tem o formato {"dados": [...], "links": [{"rel": "next", "href": ...}, ...]}.
- A paginação é por `pagina` + `itens`, com no máximo 100 itens por página
  (pedir mais que isso é ignorado em silêncio). O link "next" some na última página.
- Parâmetros podem se repetir: `mes=11&mes=12` traz os dois meses numa consulta só.
- Deputado inexistente responde 404.

Cuidados para "respeitar a API" (é um serviço público, sem cota contratada):
- pausa entre requisições;
- nova tentativa com espera exponencial (1s, 2s, 4s...) em erro de rede, 429 e 5xx;
- timeout em toda requisição (sem ele, uma conexão travada prende o ETL para sempre).
"""

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Erros em que vale a pena tentar de novo (o problema é temporário)
STATUS_TEMPORARIOS = {429, 500, 502, 503, 504}


class ErroApiCamara(Exception):
    """A API da Câmara falhou mesmo depois de todas as tentativas."""


class CamaraClient:
    ITENS_POR_PAGINA = 100  # máximo aceito pela API

    def __init__(
        self,
        base_url: str | None = None,
        pausa_segundos: float | None = None,
        timeout_segundos: float | None = None,
        max_tentativas: int | None = None,
        transport: httpx.BaseTransport | None = None,  # permite simular a API nos testes
    ):
        cfg = get_settings()
        self.pausa = cfg.etl_pausa_segundos if pausa_segundos is None else pausa_segundos
        self.max_tentativas = max_tentativas or cfg.etl_max_tentativas
        self.http = httpx.Client(
            base_url=base_url or cfg.camara_api_url,
            timeout=timeout_segundos or cfg.etl_timeout_segundos,
            headers={"Accept": "application/json", "User-Agent": "RadarDosDeputados/0.1 (projeto academico)"},
            transport=transport,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "CamaraClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ base

    def _get(self, caminho: str, params: dict[str, Any] | None = None) -> dict:
        """GET com retry e backoff exponencial. Retorna o JSON da resposta."""
        for tentativa in range(1, self.max_tentativas + 1):
            try:
                resposta = self.http.get(caminho, params=params)
                if resposta.status_code in STATUS_TEMPORARIOS:
                    raise httpx.HTTPStatusError(
                        f"status {resposta.status_code}", request=resposta.request, response=resposta
                    )
                resposta.raise_for_status()  # 4xx (ex.: 404) não adianta repetir: falha na hora
                return resposta.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as erro:
                temporario = isinstance(erro, httpx.TransportError) or (erro.response.status_code in STATUS_TEMPORARIOS)
                if not temporario or tentativa == self.max_tentativas:
                    raise ErroApiCamara(f"GET {caminho} {params} falhou: {erro}") from erro
                espera = 2 ** (tentativa - 1)  # 1s, 2s, 4s, 8s...
                log.warning(
                    "GET %s falhou (%s); tentativa %d/%d em %ds", caminho, erro, tentativa, self.max_tentativas, espera
                )
                time.sleep(espera)
            finally:
                if self.pausa:
                    time.sleep(self.pausa)
        raise AssertionError("inalcançável")

    def _paginar(self, caminho: str, params: dict[str, Any] | None = None) -> Iterator[dict]:
        """Percorre todas as páginas, entregando item por item.

        Para quando a página vem sem link "next" (ou vem vazia, por segurança).
        """
        params = {**(params or {}), "itens": self.ITENS_POR_PAGINA}
        pagina = 1
        while True:
            corpo = self._get(caminho, {**params, "pagina": pagina})
            dados = corpo.get("dados", [])
            yield from dados
            tem_proxima = any(link.get("rel") == "next" for link in corpo.get("links", []))
            if not dados or not tem_proxima:
                return
            pagina += 1

    # ---------------------------------------------------------- endpoints

    def legislatura_atual(self) -> int:
        corpo = self._get("/legislaturas", {"ordem": "DESC", "ordenarPor": "id", "itens": 1})
        return int(corpo["dados"][0]["id"])

    def listar_deputados(self, id_legislatura: int | None = None) -> list[dict]:
        """Sem legislatura: só os deputados em exercício hoje (513).
        Com legislatura: todos que exerceram mandato nela, inclusive suplentes que já saíram."""
        params = {"idLegislatura": id_legislatura} if id_legislatura else {}
        return list(self._paginar("/deputados", params))

    def detalhar_deputado(self, id_deputado: int) -> dict:
        """Detalhe de um deputado (é daqui que vem o nomeCivil)."""
        return self._get(f"/deputados/{id_deputado}")["dados"]

    def listar_despesas(self, id_deputado: int, ano: int, meses: list[int] | None = None) -> list[dict]:
        """Todas as despesas do deputado no ano (opcionalmente só nos meses indicados)."""
        params: dict[str, Any] = {"ano": ano}
        if meses:
            params["mes"] = meses  # httpx envia como mes=1&mes=2...
        return list(self._paginar(f"/deputados/{id_deputado}/despesas", params))
