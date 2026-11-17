from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._comum import check_valores, criado_em_col

TIPOS_EXECUCAO = ("carga-inicial", "atualizar", "recalcular-alertas", "gerar-resumos")
STATUS_EXECUCAO = ("rodando", "sucesso", "erro")


class ExecucaoETL(Base):
    """Log de cada execução do ETL: quando rodou, quanto trouxe e se deu erro.

    Útil para auditoria ("de quando são estes dados?") e para depurar falhas
    do job agendado sem precisar procurar em arquivos de log.
    """

    __tablename__ = "execucoes_etl"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30))
    inicio: Mapped[datetime] = criado_em_col()
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="rodando", server_default="rodando")
    registros: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    erro: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        check_valores("tipo", TIPOS_EXECUCAO, "tipo"),
        check_valores("status", STATUS_EXECUCAO, "status"),
    )
