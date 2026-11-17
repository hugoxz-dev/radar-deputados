"""Configurações da aplicação, lidas de variáveis de ambiente / arquivo .env.

Por que pydantic-settings? Ele valida os tipos (ex.: ETL_MESES_CARGA_INICIAL
precisa ser inteiro) e falha logo na inicialização se algo estiver errado,
em vez de quebrar no meio de uma requisição. E mantém os segredos fora do código.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# O .env fica na raiz do repositório (um nível acima de backend/).
# No Docker as variáveis já chegam pelo env_file do compose.
_ARQUIVO_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ARQUIVO_ENV,
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis do .env que não usamos aqui (ex.: POSTGRES_USER)
    )

    # Banco
    database_url: str = "postgresql+psycopg://radar:radar_dev@localhost:5432/radar"

    # API
    ambiente: str = "desenvolvimento"
    cors_origens: str = "http://localhost:5173"

    # Autenticação
    jwt_segredo: str = "troque-este-valor"
    jwt_expiracao_minutos: int = 1440

    # ETL
    camara_api_url: str = "https://dadosabertos.camara.leg.br/api/v2"
    etl_meses_carga_inicial: int = 12
    etl_pausa_segundos: float = 0.3
    etl_paralelismo: int = 3  # quantos deputados são baixados ao mesmo tempo
    etl_timeout_segundos: float = 30
    etl_max_tentativas: int = 5

    # Detecção de gastos fora do padrão (ver docs/metodologia.md)
    anomalia_z_limiar: float = 3.5  # regras 1 e 4: z-score robusto mínimo
    anomalia_min_grupo: int = 30  # regra 1: mínimo de notas na categoria+UF para comparar
    anomalia_concentracao_limite: float = 0.40  # regra 2: fatia mínima do maior fornecedor
    anomalia_concentracao_min_total: float = 10000  # regra 2: gasto mínimo na categoria no ano (R$)
    anomalia_concentracao_min_notas: int = 5  # regra 2: notas mínimas na categoria no ano
    anomalia_repetidas_valor_minimo: float = 100  # regra 3: ignora notas pequenas (R$)
    anomalia_repetidas_janela_dias: int = 0  # regra 3: 0 = mesma data; 3 = até 3 dias de diferença
    anomalia_mensal_razao_minima: float = 2.0  # regra 4: total do mês >= N vezes a mediana da UF
    anomalia_mensal_min_deputados: int = 5  # regra 4: mínimo de deputados da UF no mês
    # regra 4: só meses "consolidados", com pelo menos esta fração do volume típico de notas
    # (notas chegam com até 90 dias de atraso; meses recentes ficam com mediana artificialmente baixa)
    anomalia_mensal_completude_minima: float = 0.6

    # IA
    llm_provedor: str = "template"  # template | anthropic | ollama
    llm_paralelismo: int = 4  # resumos gerados ao mesmo tempo
    anthropic_api_key: str = ""
    anthropic_modelo: str = "claude-opus-5-5"
    ollama_url: str = "http://localhost:11434"
    ollama_modelo: str = "llama3.1"

    # Pagamento
    pagamento_modo: str = "simulado"  # simulado | stripe
    plano_pro_preco_centavos: int = 1990  # R$ 19,90/mês (exibido em /planos; no Stripe o preço vem do STRIPE_PRICE_ID)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    frontend_url: str = "http://localhost:5173"

    # E-mail
    email_backend: str = "console"
    smtp_host: str = "localhost"
    smtp_porta: int = 1025
    email_remetente: str = "alertas@radar-deputados.local"

    # Agendador (scheduler.py): roda o ciclo diário neste horário
    agenda_hora: int = 6
    agenda_minuto: int = 0
    agenda_fuso: str = "America/Sao_Paulo"

    @property
    def lista_cors_origens(self) -> list[str]:
        return [o.strip() for o in self.cors_origens.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Lê as configurações uma vez só e reaproveita (cache)."""
    return Settings()
