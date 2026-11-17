"""Usuários, assinaturas do plano Pro e inscrições de alerta."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._comum import check_valores, criado_em_col

PLANOS = ("free", "pro")
STATUS_ASSINATURA = ("pendente", "ativa", "cancelada", "expirada")
PROVEDORES_PAGAMENTO = ("simulado", "stripe")
TIPOS_INSCRICAO = ("deputado", "uf", "categoria")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))  # bcrypt; a senha em si nunca é guardada
    nome: Mapped[str] = mapped_column(String(150))
    # Campo "desnormalizado": dá para deduzir das assinaturas, mas guardar aqui
    # deixa a checagem de acesso Pro (feita em toda rota Pro) uma leitura simples.
    plano: Mapped[str] = mapped_column(String(10), default="free", server_default="free")
    criado_em: Mapped[datetime] = criado_em_col()

    assinaturas: Mapped[list["Assinatura"]] = relationship(back_populates="usuario")
    inscricoes: Mapped[list["InscricaoAlerta"]] = relationship(back_populates="usuario")

    __table_args__ = (check_valores("plano", PLANOS, "plano"),)


class Assinatura(Base):
    """Histórico de assinaturas: cada assinatura/cancelamento fica registrado."""

    __tablename__ = "assinaturas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pendente", server_default="pendente")
    inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provedor: Mapped[str] = mapped_column(String(20))
    # Id da sessão/assinatura no Stripe; usado pelo webhook para achar esta linha.
    referencia_externa: Mapped[str | None] = mapped_column(String(255), index=True)
    criado_em: Mapped[datetime] = criado_em_col()

    usuario: Mapped[Usuario] = relationship(back_populates="assinaturas")

    __table_args__ = (
        check_valores("status", STATUS_ASSINATURA, "status"),
        check_valores("provedor", PROVEDORES_PAGAMENTO, "provedor"),
    )


class InscricaoAlerta(Base):
    """O usuário Pro "segue" um deputado, uma UF ou uma categoria para receber alertas."""

    __tablename__ = "inscricoes_alerta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    # id do deputado, sigla da UF ou slug da categoria, conforme o tipo
    valor: Mapped[str] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criado_em: Mapped[datetime] = criado_em_col()

    usuario: Mapped[Usuario] = relationship(back_populates="inscricoes")

    __table_args__ = (
        check_valores("tipo", TIPOS_INSCRICAO, "tipo"),
        # O mesmo usuário não segue a mesma coisa duas vezes.
        UniqueConstraint("usuario_id", "tipo", "valor"),
    )
