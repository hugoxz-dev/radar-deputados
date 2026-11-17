"""Consultas agregadas usadas pela API pública.

Todas as somas e contagens são feitas no PostgreSQL (GROUP BY), não em Python:
o banco usa os índices e devolve só o resultado, em vez de trafegar 180 mil
linhas para a aplicação somar.

Convenção: `filtros` são condições extras do SQLAlchemy (ex.: Despesa.deputado_id == 10)
aplicadas junto com o filtro de período.
"""

from decimal import Decimal

from sqlalchemy import ColumnElement, Select, desc, func, select
from sqlalchemy.orm import Session

from app.models import Alerta, Categoria, Deputado, Despesa, ExecucaoETL, Fornecedor
from app.schemas.publico import (
    CategoriaOut,
    ComparacaoUF,
    FornecedorTotal,
    ItemRanking,
    ValorPorCategoria,
    ValorPorMes,
)
from app.services.categorias import nome_categoria
from app.services.periodo import Periodo

ZERO = Decimal("0.00")


def categoria_out(c: Categoria) -> CategoriaOut:
    return CategoriaOut(id=c.id, slug=c.slug, nome=nome_categoria(c.slug, c.descricao), descricao=c.descricao)


def _base(periodo: Periodo, filtros: tuple[ColumnElement[bool], ...]) -> list[ColumnElement[bool]]:
    return [periodo.filtro(Despesa.ano, Despesa.mes), *filtros]


def totais(db: Session, periodo: Periodo, *filtros) -> tuple[Decimal, int]:
    """(soma do valor líquido, quantidade de notas)."""
    total, n = db.execute(
        select(func.coalesce(func.sum(Despesa.valor_liquido), ZERO), func.count(Despesa.id))
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .where(*_base(periodo, filtros))
    ).one()
    return total, n


def por_categoria(db: Session, periodo: Periodo, *filtros) -> list[ValorPorCategoria]:
    soma = func.sum(Despesa.valor_liquido)
    linhas = db.execute(
        select(Categoria, soma, func.count(Despesa.id))
        .join(Despesa, Despesa.categoria_id == Categoria.id)
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .where(*_base(periodo, filtros))
        .group_by(Categoria.id)
        .order_by(desc(soma))
    ).all()
    total_geral = sum((linha[1] for linha in linhas), ZERO)
    return [
        ValorPorCategoria(
            categoria=categoria_out(cat),
            total=total,
            n_notas=n,
            percentual=round(float(total / total_geral * 100), 2) if total_geral else 0.0,
        )
        for cat, total, n in linhas
    ]


def por_mes(db: Session, periodo: Periodo, *filtros) -> list[ValorPorMes]:
    """Total por mês, incluindo os meses sem gasto (com zero), para o gráfico não "pular" meses."""
    linhas = db.execute(
        select(Despesa.ano, Despesa.mes, func.sum(Despesa.valor_liquido), func.count(Despesa.id))
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .where(*_base(periodo, filtros))
        .group_by(Despesa.ano, Despesa.mes)
    ).all()
    por_chave = {(ano, mes): (total, n) for ano, mes, total, n in linhas}
    return [
        ValorPorMes(
            ano=ano,
            mes=mes,
            total=por_chave.get((ano, mes), (ZERO, 0))[0],
            n_notas=por_chave.get((ano, mes), (ZERO, 0))[1],
        )
        for ano, mes in periodo.meses()
    ]


def top_fornecedores(db: Session, periodo: Periodo, deputado_id: int, limite: int = 5) -> list[FornecedorTotal]:
    soma = func.sum(Despesa.valor_liquido)
    linhas = db.execute(
        select(Fornecedor.cnpj_cpf, Fornecedor.nome, soma, func.count(Despesa.id))
        .join(Despesa, Despesa.fornecedor_id == Fornecedor.id)
        .where(periodo.filtro(Despesa.ano, Despesa.mes), Despesa.deputado_id == deputado_id)
        .group_by(Fornecedor.id)
        .order_by(desc(soma))
        .limit(limite)
    ).all()
    return [FornecedorTotal(cnpj_cpf=c, nome=n, total=t, n_notas=q) for c, n, t, q in linhas]


def totais_por_deputado(periodo: Periodo, *filtros) -> Select:
    """Subconsulta: (deputado_id, total, n_notas) no período. Base de rankings e medianas."""
    return (
        select(
            Despesa.deputado_id.label("deputado_id"),
            func.sum(Despesa.valor_liquido).label("total"),
            func.count(Despesa.id).label("n_notas"),
        )
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .where(*_base(periodo, filtros))
        .group_by(Despesa.deputado_id)
    )


def comparacao_uf(db: Session, periodo: Periodo, deputado: Deputado, total_deputado: Decimal) -> ComparacaoUF | None:
    """Compara o total do deputado com a MEDIANA dos deputados da mesma UF.

    Por que mediana e não média? Alguns poucos deputados com gasto muito alto
    puxariam a média para cima; a mediana representa o deputado "típico".
    Só entram deputados com ao menos uma nota no período.
    """
    sub = totais_por_deputado(periodo, Deputado.uf == deputado.uf).subquery()
    mediana, n = db.execute(select(func.percentile_cont(0.5).within_group(sub.c.total), func.count())).one()
    if not n or mediana is None:
        return None
    mediana = Decimal(str(mediana)).quantize(Decimal("0.01"))
    return ComparacaoUF(
        uf=deputado.uf,
        mediana_uf=mediana,
        n_deputados_uf=n,
        razao=round(float(total_deputado / mediana), 2) if mediana else None,
    )


def contar_alertas(db: Session, periodo: Periodo, *filtros) -> int:
    # Alertas anuais (mes nulo) contam se o ano se sobrepõe ao período
    return (
        db.scalar(select(func.count(Alerta.id)).where(periodo.filtro_mes_ou_ano(Alerta.ano, Alerta.mes), *filtros)) or 0
    )


def ultima_atualizacao(db: Session):
    return db.scalar(select(func.max(ExecucaoETL.fim)).where(ExecucaoETL.status == "sucesso"))


# ------------------------------------------------------------------- rankings


def ranking(db: Session, tipo: str, periodo: Periodo, filtros: list, ordem: str, limite: int) -> list[ItemRanking]:
    """Rankings por categoria, UF, partido ou deputado.

    `media_por_deputado` permite comparar grupos de tamanhos diferentes:
    SP tem 70 deputados e RR tem 8, então o total de SP é naturalmente maior.
    """
    soma = func.sum(Despesa.valor_liquido).label("total")
    n_notas = func.count(Despesa.id).label("n_notas")
    n_dep = func.count(func.distinct(Despesa.deputado_id)).label("n_deputados")
    media = (soma / func.nullif(n_dep, 0)).label("media")

    # O que muda entre os tipos é só "agrupar por quê". O resto é igual.
    agrupar_por = {
        "categoria": Categoria,
        "deputado": Deputado,
        "uf": Deputado.uf,
        "partido": Deputado.partido,
    }[tipo]

    criterio = media if ordem == "media" else soma
    linhas = db.execute(
        select(agrupar_por, soma, n_notas, n_dep, media)
        .select_from(Despesa)
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .join(Categoria, Categoria.id == Despesa.categoria_id)
        .where(periodo.filtro(Despesa.ano, Despesa.mes), *filtros)
        .group_by(Categoria.id if tipo == "categoria" else Deputado.id if tipo == "deputado" else agrupar_por)
        .order_by(desc(criterio))
        .limit(limite)
    ).all()

    itens = []
    for posicao, linha in enumerate(linhas, start=1):
        objeto, total, notas, deputados, media_valor = linha
        extra = {}
        if tipo == "categoria":
            chave, nome = objeto.slug, nome_categoria(objeto.slug, objeto.descricao)
        elif tipo == "deputado":
            chave, nome = str(objeto.id), objeto.nome
            extra = {"uf": objeto.uf, "partido": objeto.partido, "url_foto": objeto.url_foto}
        else:
            chave = nome = objeto
        itens.append(
            ItemRanking(
                posicao=posicao,
                chave=chave,
                nome=nome,
                total=total,
                n_notas=notas,
                n_deputados=deputados,
                media_por_deputado=Decimal(media_valor).quantize(Decimal("0.01")),
                **extra,
            )
        )
    return itens
