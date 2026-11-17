"""Rotas públicas dos gastos fora do padrão (alertas)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alerta, Categoria, Deputado, Despesa, Fornecedor
from app.models.alerta import REGRAS
from app.routers._comum import Paginacao, Periodo, paginacao_param, periodo_param
from app.schemas.publico import AlertaOut, ContagemRegra, DeputadoBasico, NotaDoAlerta, Pagina
from app.services import consultas
from app.services.anomalias import NOMES_REGRAS

router = APIRouter(tags=["alertas"])


Regra = Literal["valor_atipico_categoria_uf", "concentracao_fornecedor", "notas_repetidas", "gasto_mensal_atipico"]


def _filtros(
    periodo: Periodo, regra: str | None, uf: str | None, categoria: str | None, deputado_id: int | None
) -> list:
    filtros = [periodo.filtro_mes_ou_ano(Alerta.ano, Alerta.mes)]
    if regra:
        filtros.append(Alerta.regra == regra)
    if uf:
        filtros.append(Deputado.uf == uf.upper())
    if categoria:
        filtros.append(Categoria.slug == categoria)
    if deputado_id:
        filtros.append(Alerta.deputado_id == deputado_id)
    return filtros


def _consulta_alertas(db: Session, filtros: list, paginacao: Paginacao) -> Pagina[AlertaOut]:
    consulta = (
        select(Alerta, Deputado, Categoria, Despesa, Fornecedor)
        .join(Deputado, Deputado.id == Alerta.deputado_id)
        .outerjoin(Categoria, Categoria.id == Alerta.categoria_id)
        .outerjoin(Despesa, Despesa.id == Alerta.despesa_id)
        .outerjoin(Fornecedor, Fornecedor.id == Despesa.fornecedor_id)
        .where(*filtros)
    )
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    # Mais recentes primeiro; no mesmo mês, os mais intensos (score) primeiro.
    # Alertas anuais (mes nulo) vão para o fim do seu ano (coalesce 0), para não
    # tomarem o topo do feed antes dos alertas mensais mais recentes.
    ordem = [desc(Alerta.ano), desc(func.coalesce(Alerta.mes, 0)), desc(Alerta.score), desc(Alerta.id)]
    linhas = db.execute(consulta.order_by(*ordem).offset(paginacao.offset).limit(paginacao.itens)).all()

    itens = [
        AlertaOut(
            id=a.id,
            regra=a.regra,
            regra_nome=NOMES_REGRAS[a.regra],
            score=a.score,
            valor_referencia=a.valor_referencia,
            explicacao=a.explicacao,
            ano=a.ano,
            mes=a.mes,
            criado_em=a.criado_em,
            deputado=DeputadoBasico.model_validate(dep),
            categoria=consultas.categoria_out(cat) if cat else None,
            nota=NotaDoAlerta(
                id=desp.id,
                data_documento=desp.data_documento,
                valor_liquido=desp.valor_liquido,
                fornecedor_nome=forn.nome if forn else None,
                url_documento=desp.url_documento,
            )
            if desp
            else None,
        )
        for a, dep, cat, desp, forn in linhas
    ]
    return Pagina(itens=itens, total=total, pagina=paginacao.pagina, itens_por_pagina=paginacao.itens)


@router.get("/alertas", response_model=Pagina[AlertaOut], summary="Feed de gastos fora do padrão")
def listar_alertas(
    regra: Regra | None = Query(None, description="Filtrar por regra"),
    uf: str | None = Query(None, min_length=2, max_length=2),
    categoria: str | None = Query(None, description="Slug da categoria"),
    periodo: Periodo = Depends(periodo_param),
    paginacao: Paginacao = Depends(paginacao_param),
    db: Session = Depends(get_db),
):
    """Destaques estatísticos: **um gasto fora do padrão não indica irregularidade**.
    A explicação de cada regra está na página de Metodologia."""
    return _consulta_alertas(db, _filtros(periodo, regra, uf, categoria, None), paginacao)


@router.get("/alertas/por-regra", response_model=list[ContagemRegra], summary="Quantidade de alertas por regra")
def contagem_por_regra(
    uf: str | None = Query(None, min_length=2, max_length=2),
    categoria: str | None = Query(None),
    periodo: Periodo = Depends(periodo_param),
    db: Session = Depends(get_db),
):
    filtros = _filtros(periodo, None, uf, categoria, None)
    contagem = dict(
        db.execute(
            select(Alerta.regra, func.count(Alerta.id))
            .join(Deputado, Deputado.id == Alerta.deputado_id)
            .outerjoin(Categoria, Categoria.id == Alerta.categoria_id)
            .where(*filtros)
            .group_by(Alerta.regra)
        ).all()
    )
    return [ContagemRegra(regra=r, nome=NOMES_REGRAS[r], quantidade=contagem.get(r, 0)) for r in REGRAS]


@router.get("/deputados/{id_deputado}/alertas", response_model=Pagina[AlertaOut], summary="Alertas de um deputado")
def alertas_do_deputado(
    id_deputado: int,
    periodo: Periodo = Depends(periodo_param),
    paginacao: Paginacao = Depends(paginacao_param),
    db: Session = Depends(get_db),
):
    if db.get(Deputado, id_deputado) is None:
        raise HTTPException(status_code=404, detail=f"Deputado {id_deputado} não encontrado.")
    return _consulta_alertas(db, _filtros(periodo, None, None, None, id_deputado), paginacao)
