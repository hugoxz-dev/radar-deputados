"""Inscrições de alerta (plano Pro): o usuário "acompanha" um deputado, uma UF ou uma categoria
e recebe e-mail quando surgem novos gastos fora do padrão que batem com elas."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, Deputado, InscricaoAlerta, Usuario
from app.seguranca import exigir_plano_pro
from app.services.categorias import nome_categoria

router = APIRouter(prefix="/me/inscricoes", tags=["inscrições (Pro)"])

LIMITE_INSCRICOES = 50  # por usuário: evita abuso e e-mails gigantes


class InscricaoIn(BaseModel):
    tipo: Literal["deputado", "uf", "categoria"]
    valor: str = Field(min_length=1, max_length=255, description="id do deputado, sigla da UF ou slug da categoria")


class InscricaoOut(BaseModel):
    id: int
    tipo: str
    valor: str
    descricao: str  # legível: "Acácio Favacho (MDB-AP)", "Amapá (AP)", "Combustíveis e lubrificantes"
    ativo: bool
    criado_em: datetime


def _descrever(db: Session, tipo: str, valor: str) -> str | None:
    """Confere se o alvo existe e devolve o nome legível (None = não existe)."""
    if tipo == "deputado":
        deputado = db.get(Deputado, int(valor)) if valor.isdigit() else None
        return f"{deputado.nome} ({deputado.partido}-{deputado.uf})" if deputado else None
    if tipo == "uf":
        existe = db.scalar(select(func.count()).select_from(Deputado).where(Deputado.uf == valor))
        return f"Deputados de {valor}" if existe else None
    categoria = db.scalar(select(Categoria).where(Categoria.slug == valor))
    return nome_categoria(categoria.slug, categoria.descricao) if categoria else None


def _saida(db: Session, inscricao: InscricaoAlerta) -> InscricaoOut:
    return InscricaoOut(
        id=inscricao.id,
        tipo=inscricao.tipo,
        valor=inscricao.valor,
        ativo=inscricao.ativo,
        criado_em=inscricao.criado_em,
        descricao=_descrever(db, inscricao.tipo, inscricao.valor) or inscricao.valor,
    )


@router.get("", response_model=list[InscricaoOut], summary="Minhas inscrições")
def listar(usuario: Usuario = Depends(exigir_plano_pro), db: Session = Depends(get_db)):
    inscricoes = db.scalars(
        select(InscricaoAlerta).where(InscricaoAlerta.usuario_id == usuario.id).order_by(InscricaoAlerta.criado_em)
    )
    return [_saida(db, i) for i in inscricoes]


@router.post("", response_model=InscricaoOut, status_code=status.HTTP_201_CREATED, summary="Acompanhar")
def criar(dados: InscricaoIn, usuario: Usuario = Depends(exigir_plano_pro), db: Session = Depends(get_db)):
    valor = dados.valor.strip().upper() if dados.tipo == "uf" else dados.valor.strip()
    if _descrever(db, dados.tipo, valor) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Não encontramos {dados.tipo} '{valor}'.")

    existente = db.scalar(
        select(InscricaoAlerta).where(
            InscricaoAlerta.usuario_id == usuario.id, InscricaoAlerta.tipo == dados.tipo, InscricaoAlerta.valor == valor
        )
    )
    if existente:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Você já acompanha isso.")
    total = db.scalar(select(func.count()).select_from(InscricaoAlerta).where(InscricaoAlerta.usuario_id == usuario.id))
    if total >= LIMITE_INSCRICOES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Limite de {LIMITE_INSCRICOES} inscrições atingido."
        )

    inscricao = InscricaoAlerta(usuario_id=usuario.id, tipo=dados.tipo, valor=valor)
    db.add(inscricao)
    db.commit()
    db.refresh(inscricao)
    return _saida(db, inscricao)


@router.delete("/{id_inscricao}", status_code=status.HTTP_204_NO_CONTENT, summary="Deixar de acompanhar")
def remover(id_inscricao: int, usuario: Usuario = Depends(exigir_plano_pro), db: Session = Depends(get_db)):
    inscricao = db.get(InscricaoAlerta, id_inscricao)
    # Inscrição de outro usuário responde 404 (e não 403): não revela que o id existe
    if inscricao is None or inscricao.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Inscrição não encontrada.")
    db.delete(inscricao)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
