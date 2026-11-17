"""Ponto de entrada da API (FastAPI).

Rode com:  uvicorn app.main:app --reload
Documentação automática (Swagger): http://localhost:8000/docs
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routers import alertas, auth, deputados, estatisticas, export, inscricoes, planos
from app.seguranca import avisar_segredo_padrao

settings = get_settings()

app = FastAPI(
    title="Radar dos Deputados",
    description=(
        "API pública com os gastos da Cota para o Exercício da Atividade "
        "Parlamentar (CEAP) dos deputados federais. Fonte: Dados Abertos da Câmara."
    ),
    version="0.1.0",
)

# CORS: permite que o front-end (outra origem/porta) chame a API pelo navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.lista_cors_origens,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas públicas (sem login)
app.include_router(deputados.router)
app.include_router(estatisticas.router)
app.include_router(alertas.router)

# Conta, planos e recursos Pro
app.include_router(auth.router)
app.include_router(planos.router)
app.include_router(export.router)
app.include_router(inscricoes.router)

avisar_segredo_padrao()


@app.get("/health", tags=["infra"])
def health(db: Session = Depends(get_db)):
    """Verifica se a API está no ar e se consegue falar com o banco.

    Retorna 503 (serviço indisponível) se o banco não responder; assim o
    problema aparece claramente em vez de um erro 500 genérico.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as erro:  # noqa: BLE001 - queremos capturar qualquer falha de conexão
        return JSONResponse(
            status_code=503,
            content={"status": "erro", "banco": "indisponível", "detalhe": str(erro)[:200]},
        )
    return {"status": "ok", "banco": "ok", "ambiente": settings.ambiente}
