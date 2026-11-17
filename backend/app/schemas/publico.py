"""Schemas Pydantic das rotas públicas: definem o formato do JSON de resposta.

Também alimentam a documentação do /docs: cada campo aparece lá com o tipo.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

# Dinheiro: dentro do Python é Decimal (exato); no JSON sai como número.
# (Por padrão o Pydantic serializaria Decimal como texto "123.45", o que
# obrigaria o front a converter tudo.)
Valor = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]

T = TypeVar("T")


class PeriodoOut(BaseModel):
    de: str
    ate: str


class Pagina(BaseModel, Generic[T]):  # noqa: UP046 - forma de genérico documentada pelo Pydantic v2
    itens: list[T]
    total: int
    pagina: int
    itens_por_pagina: int


class CategoriaOut(BaseModel):
    id: int
    slug: str
    nome: str  # nome legível
    descricao: str  # texto original da Câmara


class DeputadoBasico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    partido: str
    uf: str
    url_foto: str | None
    em_exercicio: bool


class DeputadoResumo(DeputadoBasico):
    """Deputado + quanto gastou no período (usado na busca/listagem)."""

    total_periodo: Valor = Decimal(0)
    n_notas: int = 0


class ValorPorCategoria(BaseModel):
    categoria: CategoriaOut
    total: Valor
    n_notas: int
    percentual: float  # do total do período (0 a 100)


class ValorPorMes(BaseModel):
    ano: int
    mes: int
    total: Valor
    n_notas: int


class FornecedorTotal(BaseModel):
    cnpj_cpf: str | None
    nome: str
    total: Valor
    n_notas: int


class ComparacaoUF(BaseModel):
    uf: str
    mediana_uf: Valor  # mediana do total dos deputados da UF no período
    n_deputados_uf: int
    razao: float | None  # total do deputado / mediana (1.0 = igual à mediana)


class ResumoIAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    texto: str
    periodo: str
    modelo_usado: str
    gerado_em: datetime


class DeputadoPerfil(BaseModel):
    id: int
    nome: str
    nome_civil: str | None
    partido: str
    uf: str
    url_foto: str | None
    email: str | None
    legislatura: int
    em_exercicio: bool
    periodo: PeriodoOut
    total: Valor
    n_notas: int
    media_mensal: Valor
    por_categoria: list[ValorPorCategoria]
    por_mes: list[ValorPorMes]
    top_fornecedores: list[FornecedorTotal]
    comparacao_uf: ComparacaoUF | None
    resumo_ia: ResumoIAOut | None
    n_alertas: int


class DespesaOut(BaseModel):
    id: int
    ano: int
    mes: int
    data_documento: date | None
    categoria: CategoriaOut
    fornecedor_nome: str | None
    fornecedor_cnpj_cpf: str | None
    tipo_documento: str | None
    num_documento: str | None
    valor_documento: Valor
    valor_glosa: Valor
    valor_liquido: Valor
    url_documento: str | None


class ItemRanking(BaseModel):
    posicao: int
    chave: str  # slug da categoria, sigla da UF/partido ou id do deputado
    nome: str
    total: Valor
    n_notas: int
    n_deputados: int
    media_por_deputado: Valor
    # Só no ranking de deputados:
    uf: str | None = None
    partido: str | None = None
    url_foto: str | None = None


class Ranking(BaseModel):
    tipo: str
    periodo: PeriodoOut
    itens: list[ItemRanking]


class VisaoGeral(BaseModel):
    periodo: PeriodoOut
    total: Valor
    n_notas: int
    n_deputados_com_gasto: int
    media_por_deputado: Valor
    n_alertas: int
    categoria_mais_cara: ValorPorCategoria | None
    por_categoria: list[ValorPorCategoria]
    por_mes: list[ValorPorMes]
    ultima_atualizacao: datetime | None  # fim da última execução bem-sucedida do ETL


class Filtros(BaseModel):
    """Valores disponíveis para os filtros do front (selects de UF, partido, categoria)."""

    ufs: list[str]
    partidos: list[str]
    categorias: list[CategoriaOut]


class NotaDoAlerta(BaseModel):
    """A nota ligada ao alerta (só nas regras que olham uma nota específica)."""

    id: int
    data_documento: date | None
    valor_liquido: Valor
    fornecedor_nome: str | None
    url_documento: str | None


class AlertaOut(BaseModel):
    id: int
    regra: str
    regra_nome: str
    score: float
    valor_referencia: Valor | None
    explicacao: str
    ano: int
    mes: int | None  # nulo nos alertas do ano inteiro (concentração em fornecedor)
    criado_em: datetime
    deputado: DeputadoBasico
    categoria: CategoriaOut | None
    nota: NotaDoAlerta | None


class ContagemRegra(BaseModel):
    regra: str
    nome: str
    quantidade: int
