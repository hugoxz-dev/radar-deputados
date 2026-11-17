"""Resumos em linguagem simples dos gastos de cada deputado.

Por que usar IA aqui (e como foi limitada)
------------------------------------------
Os números do perfil (totais, categorias, fornecedores, mediana da UF,
alertas) são precisos, mas difíceis de ler para quem não está acostumado.
Um LLM transforma esses números num parágrafo curto e claro. Para que isso
seja confiável:

1. O LLM recebe APENAS DADOS AGREGADOS já calculados pelo sistema, nunca as
   notas brutas. Ele não calcula nada; só escreve.
2. O prompt proíbe opinião, acusação e números que não estejam nos dados.
3. Depois de gerado, o texto passa por `validar_numeros`: se aparecer algum
   número que não está nos dados, o texto é descartado e usamos o template.
4. Gera-se uma vez por deputado e período, e o resultado fica salvo em
   `resumos_ia` (cache). A API só lê do banco: nenhuma página espera o LLM.

Provedores (plugáveis, escolhidos por LLM_PROVEDOR no .env)
-----------------------------------------------------------
- `TemplateProvider`: SEM IA. Monta o texto com um modelo fixo. Funciona
  sempre (inclusive sem chave de API) e é o reserva dos outros dois.
- `AnthropicProvider`: Claude, via API da Anthropic (ANTHROPIC_API_KEY).
- `OllamaProvider`: modelo local via Ollama (opcional).
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import anthropic
import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Alerta, Deputado, Despesa
from app.services import consultas
from app.services.anomalias import NOMES_REGRAS
from app.services.periodo import Periodo

log = logging.getLogger(__name__)


# --------------------------------------------------------------- dados de entrada


@dataclass
class ItemValor:
    nome: str
    total: float
    percentual: float  # do total do deputado no período


@dataclass
class DadosResumo:
    """Tudo o que o LLM pode saber sobre o deputado. Só agregados."""

    nome: str
    partido: str
    uf: str
    periodo_de: str  # "dez/2025"
    periodo_ate: str  # "nov/2026"
    total: float
    n_notas: int
    media_mensal: float
    categorias: list[ItemValor] = field(default_factory=list)  # maiores primeiro
    fornecedores: list[ItemValor] = field(default_factory=list)  # top 5
    mediana_uf: float | None = None
    razao_mediana_uf: float | None = None  # total / mediana da UF
    n_deputados_uf: int | None = None
    n_alertas: int = 0
    alertas_por_regra: dict[str, int] = field(default_factory=dict)
    exemplos_alertas: list[str] = field(default_factory=list)  # até 3 explicações prontas


# --------------------------------------------------------------- formatação


def moeda(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def pct(valor: float) -> str:
    return f"{round(valor)}%"


def decimal_br(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def vezes(razao: float) -> str:
    """1.5 -> "1,50 vezes"; 1.0 -> "1,00 vez" (concordância)."""
    return f"{decimal_br(razao)} {'vez' if round(razao, 2) == 1 else 'vezes'}"


def dados_para_texto(d: DadosResumo) -> str:
    """Os dados do deputado como texto, JÁ FORMATADOS no padrão brasileiro.

    O LLM recebe os números prontos ("R$ 1.234,56", "51%") para só copiá-los,
    sem converter nem arredondar. É também a lista de números "permitidos"
    usada por validar_numeros.
    """
    linhas = [
        f"Deputado(a): {d.nome} ({d.partido}-{d.uf})",
        f"Período: {d.periodo_de} a {d.periodo_ate}",
        f"Total gasto (valor líquido reembolsado): {moeda(d.total)} em {d.n_notas} notas",
        f"Média por mês: {moeda(d.media_mensal)}",
        "Gasto por categoria (maiores primeiro):",
        *[f"- {c.nome}: {moeda(c.total)} ({pct(c.percentual)} do total)" for c in d.categorias],
        "Maiores fornecedores:",
        *[f"- {f.nome}: {moeda(f.total)} ({pct(f.percentual)} do total)" for f in d.fornecedores],
    ]
    if d.mediana_uf is not None and d.razao_mediana_uf is not None:
        linhas.append(
            f"Comparação: a mediana do total gasto pelos {d.n_deputados_uf} deputados de {d.uf} no período foi "
            f"{moeda(d.mediana_uf)}; o total deste deputado(a) equivale a {vezes(d.razao_mediana_uf)} a mediana."
        )
    linhas.append(f"Gastos fora do padrão (destaques estatísticos, não indicam irregularidade): {d.n_alertas}")
    for regra, quantidade in d.alertas_por_regra.items():
        linhas.append(f"- {regra}: {quantidade}")
    if d.exemplos_alertas:
        linhas.append("Exemplos de destaques:")
        linhas.extend(f"- {e}" for e in d.exemplos_alertas)
    return "\n".join(linhas)


# --------------------------------------------------------------- validação

# Números no formato brasileiro: 1.234,56 / 51 / 1,48 / 2026
_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _numeros(texto: str) -> set[str]:
    return set(_NUMERO.findall(texto))


def validar_numeros(texto: str, dados: DadosResumo) -> list[str]:
    """Devolve os números do texto que NÃO aparecem nos dados (lista vazia = tudo certo).

    Aceita também números pequenos (até 12), que aparecem em frases como
    "nos 12 meses" ou "3 destaques" sem serem inventados.
    """
    permitidos = _numeros(dados_para_texto(dados))
    return sorted(n for n in _numeros(texto) if n not in permitidos and not (n.isdigit() and int(n) <= 12))


# --------------------------------------------------------------- prompt

PROMPT_SISTEMA = """Você escreve resumos para um portal público de transparência sobre a Cota para o \
Exercício da Atividade Parlamentar (CEAP), a verba que reembolsa gastos do mandato dos deputados federais.

Escreva UM parágrafo de 3 a 5 frases, em português simples, para um cidadão sem conhecimento técnico.

Regras obrigatórias:
- Use SOMENTE os números fornecidos, copiados exatamente como aparecem (mesmo formato). Não calcule, \
não arredonde e não crie números novos.
- Tom neutro e informativo. Não acuse, não elogie, não dê opinião política e não especule sobre motivos.
- Para os destaques estatísticos, use apenas as expressões "gasto fora do padrão" ou "atípico". Nunca \
use as palavras "suspeito", "irregular", "fraude" ou "desvio". Se houver destaques, diga que eles não \
indicam irregularidade.
- Refira-se à pessoa pelo nome (não use "o deputado" nem "a deputada").
- Mencione: o total e o período, as principais categorias, o maior fornecedor, a comparação com a \
mediana do estado (se houver) e a quantidade de gastos fora do padrão.
- Responda apenas com o parágrafo, sem título, sem listas e sem markdown."""


def montar_mensagem(dados: DadosResumo) -> str:
    return f"Dados do deputado(a):\n\n{dados_para_texto(dados)}\n\nEscreva o resumo."


# --------------------------------------------------------------- provedores


class ErroProvedorLLM(Exception):
    """O provedor não conseguiu gerar um texto utilizável."""


class ProvedorLLM(ABC):
    """Interface comum: quem gera o texto a partir dos dados agregados."""

    @property
    @abstractmethod
    def nome_modelo(self) -> str:
        """Gravado em resumos_ia.modelo_usado (transparência sobre quem escreveu)."""

    @abstractmethod
    def gerar(self, dados: DadosResumo) -> str: ...


class TemplateProvider(ProvedorLLM):
    """Sem IA: texto montado com regras fixas. Determinístico, gratuito e sempre disponível."""

    nome_modelo = "template"

    def gerar(self, d: DadosResumo) -> str:
        frases = [
            f"Entre {d.periodo_de} e {d.periodo_ate}, {d.nome} ({d.partido}-{d.uf}) teve {moeda(d.total)} em "
            f"despesas reembolsadas pela cota parlamentar, em {d.n_notas} notas, uma média de "
            f"{moeda(d.media_mensal)} por mês."
        ]
        if d.categorias:
            principal = d.categorias[0]
            frase = f"A maior parte foi para {principal.nome} ({pct(principal.percentual)} do total)"
            if len(d.categorias) > 1:
                segunda = d.categorias[1]
                frase += f", seguida de {segunda.nome} ({pct(segunda.percentual)})"
            frases.append(frase + ".")
        if d.fornecedores:
            f = d.fornecedores[0]
            frases.append(f"O maior fornecedor foi {f.nome}, com {moeda(f.total)} ({pct(f.percentual)} do total).")
        if d.razao_mediana_uf is not None and d.mediana_uf is not None:
            if d.razao_mediana_uf > 1.1:
                posicao = "acima da"
            elif d.razao_mediana_uf < 0.9:
                posicao = "abaixo da"
            else:
                posicao = "próximo da"
            frases.append(
                f"O total ficou {posicao} mediana dos {d.n_deputados_uf} deputados de {d.uf} no período "
                f"({moeda(d.mediana_uf)}), equivalente a {vezes(d.razao_mediana_uf)} esse valor."
            )
        if d.n_alertas == 0:
            frases.append("Não foram encontrados gastos fora do padrão no período.")
        elif d.n_alertas == 1:
            frases.append(
                "Foi identificado 1 gasto fora do padrão, que é um destaque estatístico e não indica irregularidade."
            )
        else:
            frases.append(
                f"Foram identificados {d.n_alertas} gastos fora do padrão, que são destaques estatísticos e não "
                "indicam irregularidade."
            )
        return " ".join(frases)


class AnthropicProvider(ProvedorLLM):
    """Claude, via SDK oficial da Anthropic."""

    # Fallback no servidor: se o modelo recusar o pedido, a própria API tenta outro modelo.
    BETA_FALLBACK = "server-side-fallback-2026-07-01"

    def __init__(self, api_key: str, modelo: str, cliente: anthropic.Anthropic | None = None):
        self._modelo = modelo
        # `cliente` permite injetar um cliente falso nos testes (sem chamar a API de verdade)
        self.cliente = cliente or anthropic.Anthropic(api_key=api_key, timeout=60, max_retries=2)

    @property
    def nome_modelo(self) -> str:
        return self._modelo

    def gerar(self, dados: DadosResumo) -> str:
        try:
            resposta = self.cliente.beta.messages.create(
                model=self._modelo,
                max_tokens=4000,
                system=PROMPT_SISTEMA,
                messages=[{"role": "user", "content": montar_mensagem(dados)}],
                # Tarefa simples (reescrever números prontos): esforço baixo = mais rápido e barato
                output_config={"effort": "low"},
                betas=[self.BETA_FALLBACK],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as erro:
            raise ErroProvedorLLM("Chave da API da Anthropic inválida (ANTHROPIC_API_KEY).") from erro
        except anthropic.RateLimitError as erro:
            raise ErroProvedorLLM("Limite de requisições da Anthropic atingido; tente mais tarde.") from erro
        except anthropic.APIStatusError as erro:
            raise ErroProvedorLLM(f"Erro da API da Anthropic ({erro.status_code}): {erro.message}") from erro
        except anthropic.APIConnectionError as erro:
            raise ErroProvedorLLM("Sem conexão com a API da Anthropic.") from erro

        if resposta.stop_reason == "refusal":
            raise ErroProvedorLLM("O modelo recusou o pedido.")
        texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()
        if not texto:
            raise ErroProvedorLLM("Resposta vazia do modelo.")
        return texto


class OllamaProvider(ProvedorLLM):
    """Modelo local via Ollama (https://ollama.com). Útil para rodar sem internet/sem custo."""

    def __init__(self, url: str, modelo: str, transport: httpx.BaseTransport | None = None):
        self._modelo = modelo
        self.http = httpx.Client(base_url=url, timeout=120, transport=transport)

    @property
    def nome_modelo(self) -> str:
        return f"ollama:{self._modelo}"

    def gerar(self, dados: DadosResumo) -> str:
        try:
            resposta = self.http.post(
                "/api/chat",
                json={
                    "model": self._modelo,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": PROMPT_SISTEMA},
                        {"role": "user", "content": montar_mensagem(dados)},
                    ],
                },
            )
            resposta.raise_for_status()
        except httpx.HTTPError as erro:
            raise ErroProvedorLLM(f"Falha ao chamar o Ollama: {erro}") from erro
        texto = resposta.json().get("message", {}).get("content", "").strip()
        if not texto:
            raise ErroProvedorLLM("Resposta vazia do Ollama.")
        return texto


def obter_provedor(cfg: Settings) -> ProvedorLLM:
    """Escolhe o provedor pelo .env. Sem chave configurada, cai no template (e avisa)."""
    escolha = cfg.llm_provedor.strip().lower()
    if escolha == "anthropic":
        if not cfg.anthropic_api_key:
            log.warning("LLM_PROVEDOR=anthropic, mas ANTHROPIC_API_KEY está vazia: usando o template (sem IA).")
            return TemplateProvider()
        return AnthropicProvider(cfg.anthropic_api_key, cfg.anthropic_modelo)
    if escolha == "ollama":
        return OllamaProvider(cfg.ollama_url, cfg.ollama_modelo)
    if escolha != "template":
        log.warning("LLM_PROVEDOR=%r desconhecido: usando o template.", cfg.llm_provedor)
    return TemplateProvider()


def gerar_texto(provedor: ProvedorLLM, dados: DadosResumo) -> tuple[str, str]:
    """Gera o resumo e devolve (texto, modelo_usado).

    Rede de segurança: se o provedor falhar OU o texto trouxer número que não
    está nos dados, usa o template. Assim o perfil nunca fica sem resumo e
    nunca mostra número inventado.
    """
    reserva = TemplateProvider()
    if isinstance(provedor, TemplateProvider):
        return reserva.gerar(dados), reserva.nome_modelo
    try:
        texto = provedor.gerar(dados)
    except ErroProvedorLLM as erro:
        log.warning("%s falhou para %s (%s); usando o template.", provedor.nome_modelo, dados.nome, erro)
        return reserva.gerar(dados), reserva.nome_modelo

    inventados = validar_numeros(texto, dados)
    if inventados:
        log.warning("Resumo de %s trouxe números fora dos dados %s; usando o template.", dados.nome, inventados)
        return reserva.gerar(dados), reserva.nome_modelo
    return texto, provedor.nome_modelo


# --------------------------------------------------------------- dados do banco

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _rotulo_mes(aaaa_mm: str) -> str:
    # "2025-12" -> "dez/2025"
    return f"{MESES[int(aaaa_mm[5:]) - 1]}/{aaaa_mm[:4]}"


def montar_dados(db: Session, deputado: Deputado, periodo: Periodo) -> DadosResumo:
    """Reúne os agregados do deputado no período (as mesmas consultas do perfil na API)."""
    do_deputado = Despesa.deputado_id == deputado.id
    total, n_notas = consultas.totais(db, periodo, do_deputado)
    total_f = float(total)
    categorias = consultas.por_categoria(db, periodo, do_deputado)
    fornecedores = consultas.top_fornecedores(db, periodo, deputado.id)
    comparacao = consultas.comparacao_uf(db, periodo, deputado, total)

    filtro_alerta = [Alerta.deputado_id == deputado.id, periodo.filtro_mes_ou_ano(Alerta.ano, Alerta.mes)]
    por_regra = dict(db.execute(select(Alerta.regra, func.count()).where(*filtro_alerta).group_by(Alerta.regra)).all())
    exemplos = list(
        db.scalars(
            select(Alerta.explicacao)
            .where(*filtro_alerta)
            .order_by(desc(Alerta.ano), desc(func.coalesce(Alerta.mes, 0)))
            .limit(3)
        )
    )
    r = periodo.para_resposta()

    return DadosResumo(
        nome=deputado.nome,
        partido=deputado.partido,
        uf=deputado.uf,
        periodo_de=_rotulo_mes(r["de"]),
        periodo_ate=_rotulo_mes(r["ate"]),
        total=total_f,
        n_notas=n_notas,
        media_mensal=total_f / len(periodo.meses()),
        categorias=[ItemValor(c.categoria.nome, float(c.total), c.percentual) for c in categorias[:6]],
        fornecedores=[
            ItemValor(f.nome, float(f.total), float(f.total) / total_f * 100 if total_f else 0) for f in fornecedores
        ],
        mediana_uf=float(comparacao.mediana_uf) if comparacao else None,
        razao_mediana_uf=comparacao.razao if comparacao else None,
        n_deputados_uf=comparacao.n_deputados_uf if comparacao else None,
        n_alertas=sum(por_regra.values()),
        alertas_por_regra={NOMES_REGRAS[k]: v for k, v in por_regra.items()},
        exemplos_alertas=exemplos,
    )
