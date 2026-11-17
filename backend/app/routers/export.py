"""Exportação de despesas em CSV (plano Pro)."""

import csv
import io
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, Deputado, Despesa, Fornecedor, Usuario
from app.routers._comum import Periodo, periodo_param
from app.seguranca import exigir_plano_pro
from app.services.categorias import nome_categoria

router = APIRouter(prefix="/export", tags=["exportação (Pro)"])

COLUNAS = [
    "data_documento",
    "ano",
    "mes",
    "deputado_id",
    "deputado",
    "partido",
    "uf",
    "categoria",
    "fornecedor",
    "cnpj_cpf",
    "tipo_documento",
    "num_documento",
    "valor_documento",
    "valor_glosa",
    "valor_liquido",
    "url_documento",
]


def _decimal_br(valor) -> str:
    # 1234.5 -> "1234,50": vírgula decimal, para o Excel em português abrir como número
    return f"{valor:.2f}".replace(".", ",")


def _documento(cnpj_cpf: str | None) -> str:
    """CPF de pessoa física sai parcialmente oculto (LGPD), como no site; CNPJ sai completo."""
    if cnpj_cpf and len(cnpj_cpf) == 11:
        return f"***.{cnpj_cpf[3:6]}.{cnpj_cpf[6:9]}-**"
    return cnpj_cpf or ""


@router.get("/despesas.csv", summary="Exportar despesas em CSV", response_class=StreamingResponse)
def exportar_despesas(
    uf: str | None = Query(None, min_length=2, max_length=2),
    partido: str | None = Query(None),
    categoria: str | None = Query(None, description="Slug da categoria"),
    deputado_id: int | None = Query(None),
    periodo: Periodo = Depends(periodo_param),
    usuario: Usuario = Depends(exigir_plano_pro),
    db: Session = Depends(get_db),
):
    """Formato pensado para o Excel em português: separador `;`, vírgula decimal e
    UTF-8 com BOM (para os acentos aparecerem certos)."""
    filtros = [periodo.filtro(Despesa.ano, Despesa.mes)]
    if uf:
        filtros.append(Deputado.uf == uf.upper())
    if partido:
        filtros.append(func.upper(Deputado.partido) == partido.upper())
    if categoria:
        filtros.append(Categoria.slug == categoria)
    if deputado_id:
        filtros.append(Despesa.deputado_id == deputado_id)

    consulta = (
        select(Despesa, Deputado, Categoria, Fornecedor)
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .join(Categoria, Categoria.id == Despesa.categoria_id)
        .outerjoin(Fornecedor, Fornecedor.id == Despesa.fornecedor_id)
        .where(*filtros)
        .order_by(Despesa.ano, Despesa.mes, Deputado.nome, Despesa.id)
        # Lê do banco aos poucos (2 mil linhas por vez): 180 mil notas não ficam inteiras na memória
        .execution_options(yield_per=2000)
    )

    def gerar() -> Iterator[str]:
        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=";")
        buffer.write("﻿")  # BOM: avisa o Excel que o arquivo é UTF-8
        escritor.writerow(COLUNAS)
        for despesa, dep, cat, forn in db.execute(consulta):
            escritor.writerow(
                [
                    despesa.data_documento.isoformat() if despesa.data_documento else "",
                    despesa.ano,
                    despesa.mes,
                    dep.id,
                    dep.nome,
                    dep.partido,
                    dep.uf,
                    nome_categoria(cat.slug, cat.descricao),
                    forn.nome if forn else "",
                    _documento(forn.cnpj_cpf if forn else None),
                    despesa.tipo_documento or "",
                    despesa.num_documento or "",
                    _decimal_br(despesa.valor_documento),
                    _decimal_br(despesa.valor_glosa),
                    _decimal_br(despesa.valor_liquido),
                    despesa.url_documento or "",
                ]
            )
            if buffer.tell() > 64_000:  # envia em blocos de ~64 KB
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    nome = f"despesas_{periodo.chave}.csv"
    return StreamingResponse(
        gerar(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{nome}"'}
    )
