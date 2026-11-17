"""Despesas da CEAP e suas tabelas de apoio (fornecedores e categorias).

Por que fornecedor e categoria têm tabela própria (normalização)?
- O mesmo fornecedor aparece em milhares de notas; guardar o nome uma vez só
  evita repetição e permite agregações como "top fornecedores".
- As categorias (tipoDespesa) são um conjunto pequeno e fixo; com tabela
  própria, filtros e rankings por categoria usam um id inteiro indexado.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._comum import Dinheiro
from app.models.deputado import Deputado


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # CNPJ (14 dígitos) ou CPF (11 dígitos), só números. Único: é a identidade do fornecedor.
    cnpj_cpf: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(255))


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    descricao: Mapped[str] = mapped_column(String(255), unique=True)  # tipoDespesa da Câmara
    # Versão "amigável para URL" (ex.: "combustiveis-e-lubrificantes")
    slug: Mapped[str] = mapped_column(String(255), unique=True)


class Despesa(Base):
    __tablename__ = "despesas"

    # BigInteger: são centenas de milhares de notas por ano.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Sem index=True aqui de propósito: o índice composto (deputado_id, ano, mes)
    # abaixo já atende buscas só por deputado_id (é a primeira coluna dele).
    deputado_id: Mapped[int] = mapped_column(ForeignKey("deputados.id"))
    # Pode ser nulo: algumas notas vêm sem CNPJ/CPF do fornecedor na API.
    fornecedor_id: Mapped[int | None] = mapped_column(ForeignKey("fornecedores.id"), index=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), index=True)

    ano: Mapped[int] = mapped_column(SmallInteger)
    mes: Mapped[int] = mapped_column(SmallInteger)
    data_documento: Mapped[date | None] = mapped_column(Date)
    tipo_documento: Mapped[str | None] = mapped_column(String(100))
    num_documento: Mapped[str | None] = mapped_column(String(100))
    valor_documento: Mapped[Decimal] = mapped_column(Dinheiro)
    valor_glosa: Mapped[Decimal] = mapped_column(Dinheiro, default=0, server_default="0")
    # Valor efetivamente reembolsado = documento - glosa. É o que usamos nas análises.
    valor_liquido: Mapped[Decimal] = mapped_column(Dinheiro)
    url_documento: Mapped[str | None] = mapped_column(Text)
    # Texto, não número: na API as passagens do SIGEPA vêm com um GUID
    # (ex.: "D09DD946-9453-4CE1-9FE5-FB6422250F98") em vez de um código numérico.
    cod_documento: Mapped[str | None] = mapped_column(String(50))
    # Hash dos campos que identificam a nota. É UNIQUE: se o ETL buscar a mesma
    # nota de novo, o banco recusa a duplicata e o ETL faz UPDATE (upsert).
    hash_unico: Mapped[str] = mapped_column(String(64), unique=True)

    deputado: Mapped[Deputado] = relationship()
    fornecedor: Mapped[Fornecedor | None] = relationship()
    categoria: Mapped[Categoria] = relationship()

    __table_args__ = (
        # Filtros por período (rankings, visão geral, recálculo de alertas).
        Index("ix_despesas_ano_mes", "ano", "mes"),
        # A consulta mais comum: "despesas do deputado X no período Y".
        Index("ix_despesas_deputado_ano_mes", "deputado_id", "ano", "mes"),
    )
