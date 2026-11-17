"""Cadastro, login e dados do usuário logado."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.schemas.conta import AssinaturaOut, CadastroIn, LoginIn, TokenOut, UsuarioOut
from app.seguranca import criar_token, gerar_hash_senha, usuario_atual, verificar_senha
from app.services.pagamentos import assinatura_ativa, verificar_expiracao

router = APIRouter(prefix="/auth", tags=["autenticação"])


def usuario_out(db: Session, usuario: Usuario) -> UsuarioOut:
    ativa = assinatura_ativa(db, usuario)
    return UsuarioOut.model_validate(usuario).model_copy(
        update={"assinatura": AssinaturaOut.model_validate(ativa) if ativa else None}
    )


@router.post("/cadastro", response_model=TokenOut, status_code=status.HTTP_201_CREATED, summary="Criar conta")
def cadastro(dados: CadastroIn, db: Session = Depends(get_db)):
    """Cria a conta no plano grátis e já devolve o token (o usuário entra direto)."""
    if db.scalar(select(Usuario.id).where(Usuario.email == dados.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Já existe uma conta com este e-mail.")
    usuario = Usuario(nome=dados.nome.strip(), email=dados.email, senha_hash=gerar_hash_senha(dados.senha))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return TokenOut(access_token=criar_token(usuario.id), usuario=usuario_out(db, usuario))


@router.post("/login", response_model=TokenOut, summary="Entrar")
def login(dados: LoginIn, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados.email))
    # Mesma mensagem para e-mail inexistente e senha errada: não revela quais e-mails têm conta.
    if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos.")
    verificar_expiracao(db, usuario)
    return TokenOut(access_token=criar_token(usuario.id), usuario=usuario_out(db, usuario))


@router.get("/me", response_model=UsuarioOut, summary="Dados do usuário logado")
def me(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    verificar_expiracao(db, usuario)
    return usuario_out(db, usuario)
