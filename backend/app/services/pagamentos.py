"""Assinatura do plano Pro: modo simulado (demonstração) ou Stripe em modo de teste.

PAGAMENTO_MODO=simulado (padrão)
    "Assinar" ativa o Pro na hora, por 30 dias, sem cobrança. Serve para a
    demonstração e para quem roda o projeto sem conta no Stripe.

PAGAMENTO_MODO=stripe
    1. POST /planos/assinar cria uma sessão de Checkout no Stripe e grava a
       assinatura como "pendente" (referencia_externa = id da sessão).
    2. O usuário paga na página do Stripe (em modo de teste: cartão 4242 4242 4242 4242).
    3. O Stripe chama POST /planos/webhook com o evento checkout.session.completed.
       Só então o plano vira Pro. Quem confirma o pagamento é o Stripe, não o
       navegador do usuário (que poderia ser forjado).
    4. Cancelamento: a assinatura é cancelada no Stripe; o evento
       customer.subscription.deleted volta o usuário para o plano grátis.

Em ambos os modos, cada assinatura fica registrada na tabela `assinaturas`
(histórico), e `usuarios.plano` guarda o plano atual para checagem rápida.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Assinatura, Usuario

log = logging.getLogger(__name__)

DIAS_ASSINATURA_SIMULADA = 30


class ErroPagamento(Exception):
    """Erro de regra de negócio (ex.: já é Pro), com mensagem para o usuário."""

    def __init__(self, mensagem: str, status_http: int = 400):
        super().__init__(mensagem)
        self.mensagem, self.status_http = mensagem, status_http


@dataclass
class ResultadoAssinatura:
    modo: str  # "simulado" | "stripe"
    plano: str  # plano do usuário depois da operação
    checkout_url: str | None = None  # no Stripe, o front redireciona para cá
    mensagem: str = ""


# ------------------------------------------------------- regras comuns


def agora() -> datetime:
    return datetime.now(UTC)


def assinatura_ativa(db: Session, usuario: Usuario) -> Assinatura | None:
    return db.scalar(
        select(Assinatura)
        .where(Assinatura.usuario_id == usuario.id, Assinatura.status == "ativa")
        .order_by(Assinatura.id.desc())
        .limit(1)
    )


def ativar(db: Session, assinatura: Assinatura, fim: datetime | None) -> None:
    assinatura.status = "ativa"
    assinatura.inicio = agora()
    assinatura.fim = fim
    assinatura.usuario.plano = "pro"


def encerrar(db: Session, assinatura: Assinatura, status: str) -> None:
    """status: 'cancelada' (pelo usuário) ou 'expirada' (prazo venceu)."""
    assinatura.status = status
    assinatura.fim = agora()
    assinatura.usuario.plano = "free"


def verificar_expiracao(db: Session, usuario: Usuario) -> None:
    """Assinatura simulada com prazo vencido volta para o grátis (chamado ao checar acesso Pro)."""
    ativa = assinatura_ativa(db, usuario)
    if ativa and ativa.fim and ativa.fim <= agora():
        encerrar(db, ativa, "expirada")
        db.commit()
        log.info("Assinatura %d do usuário %d expirou.", ativa.id, usuario.id)


def _garantir_que_nao_e_pro(db: Session, usuario: Usuario) -> None:
    verificar_expiracao(db, usuario)
    if usuario.plano == "pro":
        raise ErroPagamento("Você já é assinante do plano Pro.", 409)


# ----------------------------------------------------------- simulado


class PagamentoSimulado:
    """Sem cobrança: ativa na hora. O registro em `assinaturas` é igual ao de verdade."""

    modo = "simulado"

    def assinar(self, db: Session, usuario: Usuario) -> ResultadoAssinatura:
        _garantir_que_nao_e_pro(db, usuario)
        assinatura = Assinatura(
            usuario=usuario,
            provedor="simulado",
            status="pendente",
            referencia_externa=f"simulado-{usuario.id}-{int(agora().timestamp())}",
        )
        db.add(assinatura)
        ativar(db, assinatura, fim=agora() + timedelta(days=DIAS_ASSINATURA_SIMULADA))
        db.commit()
        return ResultadoAssinatura(self.modo, "pro", mensagem="Plano Pro ativado (modo simulado, sem cobrança).")

    def cancelar(self, db: Session, usuario: Usuario) -> ResultadoAssinatura:
        ativa = assinatura_ativa(db, usuario)
        if ativa is None:
            raise ErroPagamento("Você não tem assinatura ativa.", 404)
        encerrar(db, ativa, "cancelada")
        db.commit()
        return ResultadoAssinatura(self.modo, "free", mensagem="Assinatura cancelada. Você voltou ao plano grátis.")

    def processar_webhook(self, db: Session, payload: bytes, assinatura_header: str | None) -> str:
        raise ErroPagamento("Webhook só existe no modo Stripe (PAGAMENTO_MODO=stripe).", 400)


# -------------------------------------------------------------- stripe


class PagamentoStripe:
    modo = "stripe"

    def __init__(self, cfg: Settings, cliente: stripe.StripeClient | None = None):
        self.cfg = cfg
        # `cliente` permite injetar um Stripe falso nos testes
        self.cliente = cliente or stripe.StripeClient(cfg.stripe_secret_key)

    def assinar(self, db: Session, usuario: Usuario) -> ResultadoAssinatura:
        _garantir_que_nao_e_pro(db, usuario)
        try:
            sessao = self.cliente.v1.checkout.sessions.create(
                params={
                    "mode": "subscription",
                    "line_items": [{"price": self.cfg.stripe_price_id, "quantity": 1}],
                    "success_url": f"{self.cfg.frontend_url}/minha-conta?assinatura=sucesso",
                    "cancel_url": f"{self.cfg.frontend_url}/planos?assinatura=cancelada",
                    "client_reference_id": str(usuario.id),
                    "customer_email": usuario.email,
                }
            )
        except stripe.StripeError as erro:
            log.error("Stripe recusou a criação do checkout: %s", erro)
            raise ErroPagamento("Não foi possível iniciar o pagamento. Tente novamente.", 502) from erro

        db.add(Assinatura(usuario=usuario, provedor="stripe", status="pendente", referencia_externa=sessao.id))
        db.commit()
        return ResultadoAssinatura(
            self.modo, usuario.plano, checkout_url=sessao.url, mensagem="Redirecionando para o pagamento."
        )

    def cancelar(self, db: Session, usuario: Usuario) -> ResultadoAssinatura:
        ativa = assinatura_ativa(db, usuario)
        if ativa is None or not ativa.referencia_externa:
            raise ErroPagamento("Você não tem assinatura ativa.", 404)
        try:
            self.cliente.v1.subscriptions.cancel(ativa.referencia_externa)
        except stripe.StripeError as erro:
            log.error("Stripe recusou o cancelamento: %s", erro)
            raise ErroPagamento("Não foi possível cancelar agora. Tente novamente.", 502) from erro
        # Encerramos já; o webhook customer.subscription.deleted, quando chegar, é idempotente.
        encerrar(db, ativa, "cancelada")
        db.commit()
        return ResultadoAssinatura(self.modo, "free", mensagem="Assinatura cancelada. Você voltou ao plano grátis.")

    def processar_webhook(self, db: Session, payload: bytes, assinatura_header: str | None) -> str:
        """Confere a assinatura criptográfica do Stripe e aplica o evento. Devolve o tipo do evento."""
        try:
            evento = self.cliente.construct_event(payload, assinatura_header, self.cfg.stripe_webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as erro:
            raise ErroPagamento("Webhook com assinatura inválida.", 400) from erro

        objeto = evento.data.object
        if evento.type == "checkout.session.completed":
            assinatura = db.scalar(select(Assinatura).where(Assinatura.referencia_externa == objeto["id"]))
            if assinatura and assinatura.status == "pendente":
                # Daqui em diante a referência é a assinatura (subscription) do Stripe, usada para cancelar
                assinatura.referencia_externa = objeto["subscription"]
                ativar(db, assinatura, fim=None)  # renovação mensal fica a cargo do Stripe
                db.commit()
                log.info("Pagamento confirmado: usuário %d agora é Pro.", assinatura.usuario_id)
        elif evento.type == "customer.subscription.deleted":
            assinatura = db.scalar(select(Assinatura).where(Assinatura.referencia_externa == objeto["id"]))
            if assinatura and assinatura.status == "ativa":
                encerrar(db, assinatura, "cancelada")
                db.commit()
        return evento.type


def obter_pagamento(cfg: Settings) -> PagamentoSimulado | PagamentoStripe:
    """Escolhe o modo pelo .env. Stripe sem chave configurada cai no simulado (e avisa)."""
    if cfg.pagamento_modo == "stripe":
        if cfg.stripe_secret_key and cfg.stripe_price_id:
            return PagamentoStripe(cfg)
        log.warning("PAGAMENTO_MODO=stripe sem STRIPE_SECRET_KEY/STRIPE_PRICE_ID: usando o modo simulado.")
    return PagamentoSimulado()
