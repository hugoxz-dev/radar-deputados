from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Deputado(Base):
    __tablename__ = "deputados"

    # Chave primária = o próprio id da Câmara (chave "natural").
    # Não usamos autoincremento: assim o ETL acha o deputado direto pelo id da API.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(150))  # nome parlamentar ("nome" na API)
    nome_civil: Mapped[str | None] = mapped_column(String(200))
    partido: Mapped[str] = mapped_column(String(30), index=True)  # siglaPartido
    uf: Mapped[str] = mapped_column(String(2), index=True)  # siglaUf
    url_foto: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(200))
    legislatura: Mapped[int] = mapped_column(Integer, index=True)  # idLegislatura
    em_exercicio: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Atualizado pelo banco a cada INSERT e pelo ETL a cada UPDATE.
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Deputado {self.id} {self.nome} ({self.partido}-{self.uf})>"
