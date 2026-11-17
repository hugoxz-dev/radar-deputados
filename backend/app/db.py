"""Conexão com o PostgreSQL via SQLAlchemy 2.0.

- `engine`: o "pool" de conexões com o banco (criado uma vez por processo).
- `SessionLocal`: fábrica de sessões; cada requisição HTTP usa a sua.
- `Base`: classe-mãe dos modelos (tabelas) que vão ficar em app/models/.
- `get_db`: dependência do FastAPI que abre a sessão e garante que ela feche.
"""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

engine = create_engine(
    get_settings().database_url,
    # pool_pre_ping testa a conexão antes de usar; evita erro se o banco reiniciou.
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Convenção de nomes para índices e restrições (PK, FK, UNIQUE, CHECK).
# Sem isso o Postgres inventa nomes aleatórios, e o Alembic não consegue
# alterar/remover essas restrições de forma previsível em migrações futuras.
CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Todos os modelos herdam daqui; o Alembic usa Base.metadata para gerar migrações."""

    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
