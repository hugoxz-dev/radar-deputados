"""Configuração do Alembic (migrações do banco).

Comandos úteis (rodar dentro de backend/ ou com `docker compose exec api ...`):
    alembic upgrade head                              # aplica todas as migrações
    alembic revision --autogenerate -m "descricao"    # gera migração a partir dos modelos
    alembic downgrade -1                              # desfaz a última migração
    alembic check                                     # confere se modelos e banco batem
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  (importa os modelos para registrá-los em Base.metadata)
from alembic import context
from app.config import get_settings
from app.db import Base

config = context.config

# A URL do banco vem do .env (via app.config), não do alembic.ini:
# assim o segredo fica num lugar só.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadados dos modelos: é comparando com eles que o --autogenerate descobre o que mudou.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo offline: gera o SQL sem conectar no banco (alembic upgrade head --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo normal: conecta no banco e aplica as migrações."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detecta também mudanças de tipo de coluna
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
