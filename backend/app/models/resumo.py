from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._comum import criado_em_col


class ResumoIA(Base):
    """Resumo em linguagem simples gerado por LLM (ou template), guardado como cache.

    A API só lê desta tabela: o LLM é chamado uma vez por deputado e período
    no ETL, nunca durante uma requisição do usuário (custo e tempo de resposta).
    """

    __tablename__ = "resumos_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deputado_id: Mapped[int] = mapped_column(ForeignKey("deputados.id", ondelete="CASCADE"))
    periodo: Mapped[str] = mapped_column(String(20))  # ex.: "2026-10" ou "12m-2026-10"
    texto: Mapped[str] = mapped_column(Text)
    modelo_usado: Mapped[str] = mapped_column(String(100))  # ex.: "claude-haiku-5-5" ou "template"
    gerado_em: Mapped[datetime] = criado_em_col()

    # Um resumo por deputado por período (o índice único também acelera a busca por deputado).
    __table_args__ = (UniqueConstraint("deputado_id", "periodo"),)
