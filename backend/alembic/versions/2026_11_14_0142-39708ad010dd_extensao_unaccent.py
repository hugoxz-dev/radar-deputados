"""Extensão unaccent: busca de deputado sem depender de acento.

Com ela, buscar "acacio" encontra "Acácio Favacho". Vem no PostgreSQL
(pacote contrib), só precisa ser ativada no banco.

Revision ID: 39708ad010dd
Revises: 0fcf707c6996
Create Date: 2026-11-14 01:42:32.901066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39708ad010dd'
down_revision: Union[str, Sequence[str], None] = '0fcf707c6996'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent")
