"""Testes da camada de IA (resumos) com DADOS FICTÍCIOS.

Nenhum teste chama a API da Anthropic de verdade: o cliente é substituído por
um objeto falso que devolve respostas prontas (ou erros). Assim os testes
rodam sem chave, sem custo e sempre com o mesmo resultado.
"""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.config import Settings
from app.models import Deputado, ResumoIA
from app.services.resumo_ia import (
    AnthropicProvider,
    DadosResumo,
    ItemValor,
    OllamaProvider,
    TemplateProvider,
    gerar_texto,
    montar_mensagem,
    obter_provedor,
    validar_numeros,
)

PROIBIDAS = ("suspeit", "fraude", "desvio")  # "irregularidade" aparece só na negação obrigatória


@pytest.fixture
def dados() -> DadosResumo:
    return DadosResumo(
        nome="Fulana de Tal (fictícia)",
        partido="PTESTE",
        uf="ZZ",
        periodo_de="dez/2025",
        periodo_ate="nov/2026",
        total=480000.0,
        n_notas=249,
        media_mensal=40000.0,
        categorias=[
            ItemValor("Divulgação da atividade parlamentar", 242540.75, 50.54),
            ItemValor("Passagens aéreas (SIGEPA)", 123486.66, 25.73),
        ],
        fornecedores=[ItemValor("EMPRESA EXEMPLO LTDA", 105000.0, 21.88)],
        mediana_uf=325071.61,
        razao_mediana_uf=1.48,
        n_deputados_uf=11,
        n_alertas=2,
        alertas_por_regra={"Notas repetidas": 2},
        exemplos_alertas=["2 notas de R$ 7.665,00 do mesmo fornecedor na mesma data (25/08/2026)."],
    )


def resposta_falsa(texto: str, stop_reason: str = "end_turn"):
    """Imita o objeto de resposta do SDK (só os campos que o código usa)."""
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=texto)])


class ClienteFalso:
    """Imita anthropic.Anthropic: guarda os parâmetros da chamada e devolve o que mandarmos."""

    def __init__(self, resposta=None, erro: Exception | None = None):
        self.chamadas: list[dict] = []
        self._resposta, self._erro = resposta, erro
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        if self._erro:
            raise self._erro
        return self._resposta


# ------------------------------------------------------------- template


def test_template_usa_os_numeros_e_a_linguagem_certa(dados):
    texto = TemplateProvider().gerar(dados)
    assert "R$ 480.000,00" in texto and "249 notas" in texto
    assert "Divulgação da atividade parlamentar (51% do total)" in texto
    assert "acima da mediana dos 11 deputados de ZZ" in texto and "1,48 vezes" in texto
    assert "não indicam irregularidade" in texto
    assert not any(p in texto.lower() for p in PROIBIDAS)
    assert "o deputado" not in texto.lower() and "a deputada" not in texto.lower()  # nome, sem supor gênero
    assert 3 <= texto.count(". ") + 1 <= 6
    assert validar_numeros(texto, dados) == []  # o template nunca inventa número


def test_template_concorda_no_singular(dados):
    dados.n_alertas = 1
    texto = TemplateProvider().gerar(dados)
    assert (
        "Foi identificado 1 gasto fora do padrão, que é um destaque estatístico e não indica irregularidade." in texto
    )


def test_template_sem_alertas_e_sem_comparacao(dados):
    dados.n_alertas, dados.mediana_uf, dados.razao_mediana_uf = 0, None, None
    texto = TemplateProvider().gerar(dados)
    assert "Não foram encontrados gastos fora do padrão" in texto
    assert "mediana" not in texto


# ------------------------------------------------------------ validação


def test_validacao_pega_numero_inventado(dados):
    assert validar_numeros("Gastou R$ 480.000,00, 1,48 vezes a mediana.", dados) == []
    assert validar_numeros("Gastou R$ 1.000.000,00 no ano.", dados) == ["1.000.000,00"]
    assert validar_numeros("Gastou 33% em táxi.", dados) == ["33"]


def test_mensagem_ao_llm_so_tem_agregados(dados):
    mensagem = montar_mensagem(dados)
    assert "R$ 480.000,00" in mensagem and "EMPRESA EXEMPLO LTDA" in mensagem
    assert "http" not in mensagem  # nada de links/notas brutas


# ------------------------------------------------------------ anthropic


def test_anthropic_gera_texto_com_parametros_corretos(dados):
    cliente = ClienteFalso(resposta_falsa("Fulana gastou R$ 480.000,00 em 249 notas, 1,48 vezes a mediana."))
    provedor = AnthropicProvider("chave-falsa", "claude-opus-5-5", cliente=cliente)

    texto, modelo = gerar_texto(provedor, dados)

    assert modelo == "claude-opus-5-5"
    assert texto.startswith("Fulana gastou")
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "claude-opus-5-5"
    assert chamada["output_config"] == {"effort": "low"}
    assert chamada["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in chamada["betas"]
    assert "Nunca" in chamada["system"] and "suspeito" in chamada["system"]  # a regra de linguagem vai no prompt
    assert chamada["messages"][0]["content"] == montar_mensagem(dados)


def test_anthropic_numero_inventado_cai_no_template(dados):
    cliente = ClienteFalso(resposta_falsa("Fulana gastou cerca de R$ 500 mil."))
    texto, modelo = gerar_texto(AnthropicProvider("x", "claude-opus-5-5", cliente=cliente), dados)
    assert modelo == "template"
    assert texto == TemplateProvider().gerar(dados)


def test_anthropic_recusa_cai_no_template(dados):
    cliente = ClienteFalso(resposta_falsa("", stop_reason="refusal"))
    _, modelo = gerar_texto(AnthropicProvider("x", "claude-opus-5-5", cliente=cliente), dados)
    assert modelo == "template"


def test_anthropic_erro_de_conexao_cai_no_template(dados):
    erro = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    _, modelo = gerar_texto(AnthropicProvider("x", "claude-opus-5-5", cliente=ClienteFalso(erro=erro)), dados)
    assert modelo == "template"


def test_sem_chave_usa_template():
    assert isinstance(obter_provedor(Settings(llm_provedor="anthropic", anthropic_api_key="")), TemplateProvider)
    assert isinstance(
        obter_provedor(Settings(llm_provedor="anthropic", anthropic_api_key="sk-teste")), AnthropicProvider
    )
    assert isinstance(obter_provedor(Settings(llm_provedor="qualquer-coisa")), TemplateProvider)


# ---------------------------------------------------------------- ollama


def test_ollama_com_api_simulada(dados):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "Fulana gastou R$ 480.000,00 em 249 notas."}})

    provedor = OllamaProvider("http://ollama.simulado", "llama3.1", transport=httpx.MockTransport(handler))
    texto, modelo = gerar_texto(provedor, dados)
    assert modelo == "ollama:llama3.1" and "480.000,00" in texto


def test_ollama_fora_do_ar_cai_no_template(dados):
    provedor = OllamaProvider(
        "http://ollama.simulado", "llama3.1", transport=httpx.MockTransport(lambda r: httpx.Response(500))
    )
    assert gerar_texto(provedor, dados)[1] == "template"


# ------------------------------------------------------------------- API


def test_perfil_mostra_o_resumo_mais_recente(cliente, db):
    db.add(Deputado(id=992_001, nome="Deputada Resumo Teste", partido="PTESTE", uf="ZZ", legislatura=57))
    db.flush()
    db.add(ResumoIA(deputado_id=992_001, periodo="2025-12_2026-11", texto="Resumo de teste.", modelo_usado="template"))
    db.flush()
    resumo = cliente.get("/deputados/992001").json()["resumo_ia"]
    assert resumo["texto"] == "Resumo de teste." and resumo["modelo_usado"] == "template"
