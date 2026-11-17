"""Alertas de gasto fora do padrão (gerados pelas regras de services/anomalias.py).

Nomenclatura obrigatória: "gasto fora do padrão" / "atípico". Um alerta é um
destaque estatístico, não indica irregularidade.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Float, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._comum import Dinheiro, check_valores, criado_em_col
from app.models.despesa import Despesa

# As quatro regras da metodologia
REGRAS = ("valor_atipico_categoria_uf", "concentracao_fornecedor", "notas_repetidas", "gasto_mensal_atipico")


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Preenchido nas regras que olham uma nota específica (valor atípico, notas repetidas).
    # Fica nulo nas regras agregadas (concentração, gasto mensal), que não têm uma nota só.
    despesa_id: Mapped[int | None] = mapped_column(ForeignKey("despesas.id", ondelete="CASCADE"), index=True)
    # Contexto do alerta: sempre preenchido, para filtrar o feed e casar com as inscrições
    # (deputado / UF / categoria) sem precisar juntar com despesas.
    deputado_id: Mapped[int] = mapped_column(ForeignKey("deputados.id"), index=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"), index=True)
    ano: Mapped[int] = mapped_column(SmallInteger)
    mes: Mapped[int | None] = mapped_column(SmallInteger)

    regra: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float)  # intensidade (ex.: z-score robusto, % de concentração)
    valor_referencia: Mapped[Decimal | None] = mapped_column(Dinheiro)  # ex.: mediana usada na comparação
    explicacao: Mapped[str] = mapped_column(Text)  # texto legível para o cidadão
    # Identificador estável do alerta (ex.: "valor_atipico_categoria_uf:despesa:123").
    # Ao recalcular, o mesmo achado gera a mesma chave: não duplica, e dá para saber
    # quais alertas são realmente novos (para notificar os inscritos).
    chave: Mapped[str] = mapped_column(String(200), unique=True)
    criado_em: Mapped[datetime] = criado_em_col()

    despesa: Mapped[Despesa | None] = relationship()

    __table_args__ = (
        check_valores("regra", REGRAS, "regra"),
        Index("ix_alertas_ano_mes", "ano", "mes"),
        Index("ix_alertas_criado_em", "criado_em"),
    )
