"""Peças reaproveitadas pelos modelos."""

from sqlalchemy import CheckConstraint, DateTime, Numeric, func
from sqlalchemy.orm import mapped_column

# Dinheiro sempre como NUMERIC(12,2): valor exato em centavos.
# float/double acumulam erro de arredondamento nas somas (0.1 + 0.2 != 0.3).
Dinheiro = Numeric(12, 2)


def criado_em_col():
    """Coluna de data/hora preenchida pelo próprio banco no INSERT (com fuso horário)."""
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def check_valores(coluna: str, valores: tuple[str, ...], nome: str) -> CheckConstraint:
    """Restrição CHECK que só aceita os valores listados.

    Usamos texto + CHECK em vez de ENUM do Postgres porque é mais simples
    de evoluir (acrescentar um valor novo não exige ALTER TYPE).
    """
    lista = ", ".join(f"'{v}'" for v in valores)
    return CheckConstraint(f"{coluna} IN ({lista})", name=nome)
