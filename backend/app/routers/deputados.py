"""Rotas públicas de deputados e das despesas de cada deputado."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alerta, Categoria, Deputado, Despesa, Fornecedor, ResumoIA
from app.routers._comum import Paginacao, Periodo, paginacao_param, periodo_param
from app.schemas.publico import DeputadoPerfil, DeputadoResumo, DespesaOut, Pagina, ResumoIAOut
from app.services import consultas

router = APIRouter(prefix="/deputados", tags=["deputados"])


@router.get("", response_model=Pagina[DeputadoResumo], summary="Buscar deputados")
def listar_deputados(
    busca: str | None = Query(None, min_length=2, description="Parte do nome (ignora acentos e maiúsculas)"),
    uf: str | None = Query(None, min_length=2, max_length=2, description="Sigla da UF, ex.: MA"),
    partido: str | None = Query(None, description="Sigla do partido, ex.: PT"),
    em_exercicio: bool | None = Query(None, description="true = só quem está no cargo hoje"),
    ordenar: Literal["nome", "total"] = Query("nome", description="nome (A-Z) ou total gasto (maior primeiro)"),
    periodo: Periodo = Depends(periodo_param),
    paginacao: Paginacao = Depends(paginacao_param),
    db: Session = Depends(get_db),
):
    # Total gasto de cada deputado no período (subconsulta). LEFT JOIN: quem
    # não gastou nada também aparece, com total zero.
    totais = consultas.totais_por_deputado(periodo).subquery()
    total = func.coalesce(totais.c.total, 0)

    filtros = []
    if busca:
        termo = f"%{busca.strip()}%"
        filtros.append(
            or_(
                func.unaccent(Deputado.nome).ilike(func.unaccent(termo)),
                func.unaccent(Deputado.nome_civil).ilike(func.unaccent(termo)),
            )
        )
    if uf:
        filtros.append(Deputado.uf == uf.upper())
    if partido:
        filtros.append(func.upper(Deputado.partido) == partido.upper())
    if em_exercicio is not None:
        filtros.append(Deputado.em_exercicio == em_exercicio)

    consulta = (
        select(Deputado, total, func.coalesce(totais.c.n_notas, 0))
        .outerjoin(totais, totais.c.deputado_id == Deputado.id)
        .where(*filtros)
    )
    quantidade = db.scalar(select(func.count()).select_from(consulta.subquery()))
    ordem = [desc(total), Deputado.nome] if ordenar == "total" else [Deputado.nome]
    linhas = db.execute(consulta.order_by(*ordem).offset(paginacao.offset).limit(paginacao.itens)).all()

    itens = [
        DeputadoResumo.model_validate(dep).model_copy(update={"total_periodo": t, "n_notas": n}) for dep, t, n in linhas
    ]
    return Pagina(itens=itens, total=quantidade, pagina=paginacao.pagina, itens_por_pagina=paginacao.itens)


def _obter_deputado(db: Session, id_deputado: int) -> Deputado:
    deputado = db.get(Deputado, id_deputado)
    if deputado is None:
        raise HTTPException(status_code=404, detail=f"Deputado {id_deputado} não encontrado.")
    return deputado


@router.get("/{id_deputado}", response_model=DeputadoPerfil, summary="Perfil do deputado com totais")
def perfil(id_deputado: int, periodo: Periodo = Depends(periodo_param), db: Session = Depends(get_db)):
    dep = _obter_deputado(db, id_deputado)
    do_deputado = Despesa.deputado_id == id_deputado

    total, n_notas = consultas.totais(db, periodo, do_deputado)
    resumo = db.scalar(
        select(ResumoIA).where(ResumoIA.deputado_id == id_deputado).order_by(desc(ResumoIA.gerado_em)).limit(1)
    )
    return DeputadoPerfil(
        id=dep.id,
        nome=dep.nome,
        nome_civil=dep.nome_civil,
        partido=dep.partido,
        uf=dep.uf,
        url_foto=dep.url_foto,
        email=dep.email,
        legislatura=dep.legislatura,
        em_exercicio=dep.em_exercicio,
        periodo=periodo.para_resposta(),
        total=total,
        n_notas=n_notas,
        media_mensal=(total / len(periodo.meses())).quantize(consultas.ZERO),
        por_categoria=consultas.por_categoria(db, periodo, do_deputado),
        por_mes=consultas.por_mes(db, periodo, do_deputado),
        top_fornecedores=consultas.top_fornecedores(db, periodo, id_deputado),
        comparacao_uf=consultas.comparacao_uf(db, periodo, dep, total),
        resumo_ia=ResumoIAOut.model_validate(resumo) if resumo else None,
        n_alertas=consultas.contar_alertas(db, periodo, Alerta.deputado_id == id_deputado),
    )


@router.get("/{id_deputado}/despesas", response_model=Pagina[DespesaOut], summary="Notas do deputado")
def despesas_do_deputado(
    id_deputado: int,
    categoria: str | None = Query(None, description="Slug da categoria, ex.: combustiveis-e-lubrificantes"),
    ordenar: Literal["data", "valor"] = Query(
        "data", description="data (mais recente primeiro) ou valor (maior primeiro)"
    ),
    periodo: Periodo = Depends(periodo_param),
    paginacao: Paginacao = Depends(paginacao_param),
    db: Session = Depends(get_db),
):
    _obter_deputado(db, id_deputado)
    filtros = [Despesa.deputado_id == id_deputado, periodo.filtro(Despesa.ano, Despesa.mes)]
    if categoria:
        filtros.append(Categoria.slug == categoria)

    consulta = (
        select(Despesa, Categoria, Fornecedor)
        .join(Categoria, Categoria.id == Despesa.categoria_id)
        .outerjoin(Fornecedor, Fornecedor.id == Despesa.fornecedor_id)
        .where(*filtros)
    )
    quantidade = db.scalar(select(func.count()).select_from(consulta.subquery()))
    if ordenar == "valor":
        ordem = [desc(Despesa.valor_liquido), desc(Despesa.id)]
    else:
        # Notas sem data vão para o fim; desempate pelo mês de competência.
        ordem = [desc(Despesa.ano), desc(Despesa.mes), Despesa.data_documento.desc().nulls_last(), desc(Despesa.id)]
    linhas = db.execute(consulta.order_by(*ordem).offset(paginacao.offset).limit(paginacao.itens)).all()

    itens = [
        DespesaOut(
            id=d.id,
            ano=d.ano,
            mes=d.mes,
            data_documento=d.data_documento,
            categoria=consultas.categoria_out(c),
            fornecedor_nome=f.nome if f else None,
            fornecedor_cnpj_cpf=f.cnpj_cpf if f else None,
            tipo_documento=d.tipo_documento,
            num_documento=d.num_documento,
            valor_documento=d.valor_documento,
            valor_glosa=d.valor_glosa,
            valor_liquido=d.valor_liquido,
            url_documento=d.url_documento,
        )
        for d, c, f in linhas
    ]
    return Pagina(itens=itens, total=quantidade, pagina=paginacao.pagina, itens_por_pagina=paginacao.itens)
