"""Rotas públicas agregadas: rankings, visão geral e valores para filtros."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, Deputado, Despesa
from app.routers._comum import Periodo, periodo_param
from app.schemas.publico import Filtros, Ranking, VisaoGeral
from app.services import consultas

router = APIRouter(tags=["estatísticas"])


@router.get("/rankings", response_model=Ranking, summary="Rankings de gasto")
def rankings(
    tipo: Literal["categoria", "uf", "partido", "deputado"] = Query("categoria", description="Agrupar por"),
    categoria: str | None = Query(None, description="Filtrar por categoria (slug)"),
    uf: str | None = Query(None, min_length=2, max_length=2, description="Filtrar por UF"),
    partido: str | None = Query(None, description="Filtrar por partido"),
    ordem: Literal["total", "media"] = Query(
        "total", description="total gasto ou média por deputado (mais justo para comparar UFs e partidos)"
    ),
    limite: int = Query(30, ge=1, le=600),
    periodo: Periodo = Depends(periodo_param),
    db: Session = Depends(get_db),
):
    """Exemplos: `?tipo=uf&ordem=media`, `?tipo=deputado&categoria=combustiveis-e-lubrificantes`.

    Observação: o partido é o atual de cada deputado (a API da Câmara não
    informa o partido na data de cada nota).
    """
    filtros = []
    if categoria:
        filtros.append(Categoria.slug == categoria)
    if uf:
        filtros.append(Deputado.uf == uf.upper())
    if partido:
        filtros.append(func.upper(Deputado.partido) == partido.upper())
    itens = consultas.ranking(db, tipo, periodo, filtros, ordem, limite)
    return Ranking(tipo=tipo, periodo=periodo.para_resposta(), itens=itens)


@router.get("/estatisticas/visao-geral", response_model=VisaoGeral, summary="Números gerais do período")
def visao_geral(periodo: Periodo = Depends(periodo_param), db: Session = Depends(get_db)):
    total, n_notas = consultas.totais(db, periodo)
    n_deputados = (
        db.scalar(
            select(func.count(func.distinct(Despesa.deputado_id))).where(periodo.filtro(Despesa.ano, Despesa.mes))
        )
        or 0
    )
    categorias = consultas.por_categoria(db, periodo)
    return VisaoGeral(
        periodo=periodo.para_resposta(),
        total=total,
        n_notas=n_notas,
        n_deputados_com_gasto=n_deputados,
        media_por_deputado=(total / n_deputados).quantize(consultas.ZERO) if n_deputados else consultas.ZERO,
        n_alertas=consultas.contar_alertas(db, periodo),
        categoria_mais_cara=categorias[0] if categorias else None,
        por_categoria=categorias,
        por_mes=consultas.por_mes(db, periodo),
        ultima_atualizacao=consultas.ultima_atualizacao(db),
    )


@router.get("/filtros", response_model=Filtros, summary="Valores disponíveis para os filtros")
def filtros(db: Session = Depends(get_db)):
    return Filtros(
        ufs=list(db.scalars(select(Deputado.uf).distinct().order_by(Deputado.uf))),
        partidos=list(db.scalars(select(Deputado.partido).distinct().order_by(Deputado.partido))),
        categorias=[consultas.categoria_out(c) for c in db.scalars(select(Categoria).order_by(Categoria.descricao))],
    )
