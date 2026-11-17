"""Autenticação: hash de senha (bcrypt), token JWT e dependências de acesso do FastAPI.

Fluxo:
1. POST /auth/login confere a senha e devolve um token JWT.
2. O front guarda o token e o envia em toda requisição: `Authorization: Bearer <token>`.
3. As dependências abaixo leem o token e descobrem quem é o usuário:
   - usuario_opcional: rotas públicas que mudam um pouco para logados;
   - usuario_atual: exige login (401 se não tiver);
   - exigir_plano_pro: exige login E plano Pro (403 se for grátis).
"""

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Usuario
from app.services.pagamentos import verificar_expiracao

log = logging.getLogger(__name__)

ALGORITMO_JWT = "HS256"
# HTTPBearer faz aparecer o botão "Authorize" no /docs (cole o token lá).
# auto_error=False: quem decide se o token é obrigatório são as dependências abaixo.
esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT recebido em POST /auth/login")

MENSAGEM_PRO = "Este recurso é exclusivo do plano Pro. Assine em /planos para liberar."


# ------------------------------------------------------------------ senha


def gerar_hash_senha(senha: str) -> str:
    """bcrypt: hash lento de propósito e com "sal" aleatório. Mesmo que o banco vaze,
    descobrir as senhas exige tentar uma por uma, e cada tentativa é cara."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha: str, hash_salvo: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_salvo.encode("ascii"))
    except ValueError:  # hash corrompido ou senha > 72 bytes
        return False


# ------------------------------------------------------------------- token


def criar_token(usuario_id: int) -> str:
    cfg = get_settings()
    agora = datetime.now(UTC)
    payload = {"sub": str(usuario_id), "iat": agora, "exp": agora + timedelta(minutes=cfg.jwt_expiracao_minutos)}
    return jwt.encode(payload, cfg.jwt_segredo, algorithm=ALGORITMO_JWT)


def ler_token(token: str) -> int | None:
    """Devolve o id do usuário, ou None se o token for inválido ou estiver expirado."""
    try:
        payload = jwt.decode(token, get_settings().jwt_segredo, algorithms=[ALGORITMO_JWT])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# ------------------------------------------------------------ dependências


def _nao_autenticado(detalhe: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detalhe, headers={"WWW-Authenticate": "Bearer"})


def usuario_opcional(
    credenciais: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Usuario | None:
    """Sem token: None (visitante). Com token inválido: 401 (melhor avisar do que ignorar)."""
    if credenciais is None:
        return None
    usuario_id = ler_token(credenciais.credentials)
    usuario = db.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None:
        raise _nao_autenticado("Sessão inválida ou expirada. Entre novamente.")
    return usuario


def usuario_atual(usuario: Usuario | None = Depends(usuario_opcional)) -> Usuario:
    if usuario is None:
        raise _nao_autenticado("É preciso entrar na sua conta para usar este recurso.")
    return usuario


def exigir_plano_pro(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> Usuario:
    """Bloqueia rotas Pro: 403 com mensagem clara para quem é do plano grátis.

    Antes de checar, encerra a assinatura se o prazo dela já venceu (modo simulado).
    """
    verificar_expiracao(db, usuario)
    if usuario.plano != "pro":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=MENSAGEM_PRO)
    return usuario


def avisar_segredo_padrao() -> None:
    """Chamado na inicialização: o segredo do JWT de exemplo não pode ir para produção."""
    cfg = get_settings()
    if cfg.jwt_segredo == "troque-este-valor":
        nivel = log.error if cfg.ambiente == "producao" else log.warning
        nivel("JWT_SEGREDO está com o valor de exemplo. Gere outro (ver .env.example) antes de publicar.")
