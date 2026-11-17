"""Planos (grátis x Pro) e assinatura."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Usuario
from app.schemas.conta import AssinaturaResultado, PlanoInfo, PlanosOut
from app.seguranca import usuario_atual
from app.services.pagamentos import ErroPagamento, obter_pagamento

router = APIRouter(prefix="/planos", tags=["planos"])

RECURSOS_GRATIS = [
    "Painel completo: perfis, gráficos, rankings e notas",
    "Gastos fora do padrão e resumos em linguagem simples",
    "Últimos 12 meses",
]
RECURSOS_PRO = [
    "Tudo do plano grátis",
    "Alertas por e-mail de deputados, estados ou categorias que você acompanha",
    "Exportação das despesas em CSV, com filtros",
    "Histórico completo: qualquer período disponível na base",
]


def _executar(acao):
    """Converte erros de regra de negócio (ErroPagamento) em respostas HTTP com mensagem."""
    try:
        return acao()
    except ErroPagamento as erro:
        raise HTTPException(erro.status_http, detail=erro.mensagem) from erro


@router.get("", response_model=PlanosOut, summary="Planos disponíveis")
def listar_planos():
    cfg = get_settings()
    return PlanosOut(
        modo_pagamento=obter_pagamento(cfg).modo,
        planos=[
            PlanoInfo(id="free", nome="Grátis", preco_mensal=0, recursos=RECURSOS_GRATIS),
            PlanoInfo(id="pro", nome="Pro", preco_mensal=cfg.plano_pro_preco_centavos / 100, recursos=RECURSOS_PRO),
        ],
    )


@router.post("/assinar", response_model=AssinaturaResultado, summary="Assinar o plano Pro")
def assinar(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Modo simulado: ativa na hora. Modo Stripe: devolve `checkout_url` para o pagamento."""
    resultado = _executar(lambda: obter_pagamento(get_settings()).assinar(db, usuario))
    return AssinaturaResultado(**vars(resultado))


@router.post("/cancelar", response_model=AssinaturaResultado, summary="Cancelar a assinatura")
def cancelar(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    resultado = _executar(lambda: obter_pagamento(get_settings()).cancelar(db, usuario))
    return AssinaturaResultado(**vars(resultado))


@router.post("/webhook", summary="Webhook do Stripe", include_in_schema=True)
async def webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """Chamado pelo Stripe (não pelo front). A assinatura do cabeçalho prova que o evento veio dele."""
    payload = await request.body()  # corpo cru: a verificação da assinatura exige os bytes originais
    tipo = _executar(lambda: obter_pagamento(get_settings()).processar_webhook(db, payload, stripe_signature))
    return {"recebido": tipo}
