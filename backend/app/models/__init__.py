"""Modelos SQLAlchemy (tabelas do banco).

Importar tudo aqui garante que o Alembic "enxergue" todas as tabelas
em Base.metadata ao gerar migrações.
"""

from app.models.alerta import Alerta
from app.models.deputado import Deputado
from app.models.despesa import Categoria, Despesa, Fornecedor
from app.models.execucao_etl import ExecucaoETL
from app.models.resumo import ResumoIA
from app.models.usuario import Assinatura, InscricaoAlerta, Usuario

__all__ = [
    "Alerta",
    "Assinatura",
    "Categoria",
    "Deputado",
    "Despesa",
    "ExecucaoETL",
    "Fornecedor",
    "InscricaoAlerta",
    "ResumoIA",
    "Usuario",
]
