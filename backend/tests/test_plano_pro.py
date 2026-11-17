"""Testes de autenticação, regras de acesso do plano Pro, pagamento e exportação.

Dados FICTÍCIOS (UF "ZZ", e-mails @exemplo.invalido), desfeitos pelo rollback da fixture.
O Stripe é simulado: nenhuma chamada sai para a internet. A verificação de
assinatura do webhook, porém, é a do SDK real do Stripe (HMAC de verdade).
"""

import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import stripe
from sqlalchemy import select

from app.config import Settings
from app.models import Assinatura, Categoria, Deputado, Despesa, Fornecedor, Usuario
from app.routers import planos as rota_planos
from app.services import pagamentos
from app.services.pagamentos import PagamentoStripe

SENHA = "senha-de-teste-123"


def cadastrar(cliente, email="pessoa@exemplo.invalido", nome="Pessoa Teste") -> dict:
    r = cliente.post("/auth/cadastro", json={"nome": nome, "email": email, "senha": SENHA})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def despesas_zz(db):
    """Duas notas fictícias em ZZ: uma de empresa (CNPJ) e uma de pessoa física (CPF)."""
    cat = Categoria(descricao="CATEGORIA TESTE EXPORT", slug="categoria-teste-export")
    empresa = Fornecedor(cnpj_cpf="00000000000191", nome="EMPRESA TESTE LTDA")
    pessoa = Fornecedor(cnpj_cpf="12345678901", nome="PESSOA FISICA TESTE")
    db.add_all(
        [cat, empresa, pessoa, Deputado(id=993_001, nome="Deputado Export", partido="PT", uf="ZZ", legislatura=57)]
    )
    db.flush()
    for i, forn in enumerate([empresa, pessoa]):
        db.add(
            Despesa(
                deputado_id=993_001,
                categoria_id=cat.id,
                fornecedor_id=forn.id,
                ano=2026,
                mes=10,
                valor_documento=Decimal("1234.50"),
                valor_liquido=Decimal("1234.50"),
                hash_unico=f"teste-export-{i}",
            )
        )
    db.flush()


# --------------------------------------------------------------- autenticação


def test_cadastro_login_e_me(cliente):
    cabecalho = cadastrar(cliente, email="Maiusculas@Exemplo.INVALIDO")
    me = cliente.get("/auth/me", headers=cabecalho).json()
    assert me["email"] == "maiusculas@exemplo.invalido"  # e-mail guardado em minúsculas
    assert me["plano"] == "free" and me["assinatura"] is None

    r = cliente.post("/auth/login", json={"email": "MAIUSCULAS@exemplo.invalido", "senha": SENHA})
    assert r.status_code == 200 and r.json()["access_token"]


def test_senha_guardada_so_como_hash(cliente, db):
    cadastrar(cliente)
    usuario = db.scalar(select(Usuario).where(Usuario.email == "pessoa@exemplo.invalido"))
    assert SENHA not in usuario.senha_hash and usuario.senha_hash.startswith("$2")  # formato bcrypt


def test_email_repetido_da_409(cliente):
    cadastrar(cliente)
    r = cliente.post("/auth/cadastro", json={"nome": "Outra", "email": "pessoa@exemplo.invalido", "senha": SENHA})
    assert r.status_code == 409


@pytest.mark.parametrize("senha", ["curta", "á" * 40])  # 5 caracteres; 80 bytes (passa do limite do bcrypt)
def test_senha_invalida_da_422(cliente, senha):
    r = cliente.post("/auth/cadastro", json={"nome": "Teste", "email": "x@exemplo.invalido", "senha": senha})
    assert r.status_code == 422


def test_login_errado_nao_revela_se_email_existe(cliente):
    cadastrar(cliente)
    errada = cliente.post("/auth/login", json={"email": "pessoa@exemplo.invalido", "senha": "errada-123"})
    inexistente = cliente.post("/auth/login", json={"email": "ninguem@exemplo.invalido", "senha": "errada-123"})
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()


def test_token_invalido_ou_ausente(cliente):
    assert cliente.get("/auth/me").status_code == 401
    assert cliente.get("/auth/me", headers={"Authorization": "Bearer token-falso"}).status_code == 401


# --------------------------------------------------------- regras do plano Pro


def test_free_recebe_403_e_sem_login_401(cliente):
    cabecalho = cadastrar(cliente)
    r = cliente.get("/export/despesas.csv", headers=cabecalho)
    assert r.status_code == 403
    assert "exclusivo do plano Pro" in r.json()["detail"]
    assert cliente.get("/export/despesas.csv").status_code == 401


def test_fluxo_completo_assinar_exportar_cancelar(cliente, despesas_zz):
    cabecalho = cadastrar(cliente)

    r = cliente.post("/planos/assinar", headers=cabecalho)
    assert r.json()["plano"] == "pro" and r.json()["modo"] == "simulado"
    assert cliente.post("/planos/assinar", headers=cabecalho).status_code == 409  # já é Pro

    csv_resp = cliente.get("/export/despesas.csv?uf=ZZ&de=2026-10&ate=2026-10", headers=cabecalho)
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-disposition"].endswith('.csv"')
    texto = csv_resp.content.decode("utf-8")
    assert texto.startswith("﻿")  # BOM para o Excel
    linhas = texto.lstrip("﻿").strip().splitlines()
    assert linhas[0].startswith("data_documento;ano;mes;deputado_id")
    assert len(linhas) == 3  # cabeçalho + 2 notas
    assert "1234,50" in linhas[1]  # vírgula decimal
    assert "00000000000191" in texto  # CNPJ completo
    assert "***.456.789-**" in texto and "12345678901" not in texto  # CPF oculto (LGPD)

    assert cliente.post("/planos/cancelar", headers=cabecalho).json()["plano"] == "free"
    assert cliente.get("/export/despesas.csv", headers=cabecalho).status_code == 403


def test_assinatura_vencida_volta_para_gratis(cliente, db):
    cabecalho = cadastrar(cliente)
    cliente.post("/planos/assinar", headers=cabecalho)
    assinatura = db.scalar(select(Assinatura).where(Assinatura.status == "ativa").order_by(Assinatura.id.desc()))
    assinatura.fim = pagamentos.agora() - timedelta(minutes=1)
    db.flush()

    assert cliente.get("/export/despesas.csv", headers=cabecalho).status_code == 403
    assert cliente.get("/auth/me", headers=cabecalho).json()["plano"] == "free"
    db.refresh(assinatura)
    assert assinatura.status == "expirada"


def test_historico_completo_so_para_pro(cliente):
    antigo = "/deputados?de=2020-01&ate=2020-12"
    assert cliente.get(antigo).status_code == 403
    cabecalho = cadastrar(cliente)
    assert cliente.get(antigo, headers=cabecalho).status_code == 403
    cliente.post("/planos/assinar", headers=cabecalho)
    assert cliente.get(antigo, headers=cabecalho).status_code == 200
    assert cliente.get("/deputados").status_code == 200  # últimos 12 meses continuam públicos


# ---------------------------------------------------------------------- Stripe

SEGREDO_WEBHOOK = "whsec_teste"


class StripeFalso:
    """Imita o StripeClient: checkout e cancelamento falsos; verificação de webhook REAL."""

    def __init__(self):
        self.cancelados: list[str] = []
        self._real = stripe.StripeClient("sk_test_falso")
        sessoes = SimpleNamespace(
            create=lambda params: SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.test/cs_test_123")
        )
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(sessions=sessoes),
            subscriptions=SimpleNamespace(cancel=self.cancelados.append),
        )

    def construct_event(self, payload, sig_header, secret):
        return self._real.construct_event(payload, sig_header, secret)


def evento_assinado(tipo: str, objeto: dict, segredo: str = SEGREDO_WEBHOOK) -> tuple[bytes, str]:
    """Monta um evento como o Stripe enviaria, com o cabeçalho Stripe-Signature (HMAC-SHA256)."""
    payload = json.dumps({"id": "evt_teste", "object": "event", "type": tipo, "data": {"object": objeto}}).encode()
    momento = int(time.time())
    assinatura = hmac.new(segredo.encode(), f"{momento}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, f"t={momento},v1={assinatura}"


@pytest.fixture
def stripe_falso(monkeypatch):
    falso = StripeFalso()
    cfg = Settings(
        pagamento_modo="stripe",
        stripe_secret_key="sk_test_falso",
        stripe_price_id="price_teste",
        stripe_webhook_secret=SEGREDO_WEBHOOK,
    )
    monkeypatch.setattr(rota_planos, "obter_pagamento", lambda _cfg: PagamentoStripe(cfg, cliente=falso))
    return falso


def test_stripe_assinatura_so_ativa_depois_do_webhook(cliente, db, stripe_falso):
    cabecalho = cadastrar(cliente)
    r = cliente.post("/planos/assinar", headers=cabecalho).json()
    assert r["checkout_url"] == "https://checkout.stripe.test/cs_test_123"
    assert r["plano"] == "free"  # ainda não pagou
    assert cliente.get("/export/despesas.csv", headers=cabecalho).status_code == 403

    payload, assinatura = evento_assinado(
        "checkout.session.completed", {"id": "cs_test_123", "object": "checkout.session", "subscription": "sub_123"}
    )
    resposta = cliente.post("/planos/webhook", content=payload, headers={"Stripe-Signature": assinatura})
    assert resposta.status_code == 200 and resposta.json() == {"recebido": "checkout.session.completed"}

    me = cliente.get("/auth/me", headers=cabecalho).json()
    assert me["plano"] == "pro" and me["assinatura"]["provedor"] == "stripe"

    # Cancelar chama o Stripe com o id da assinatura (não da sessão de checkout)
    cliente.post("/planos/cancelar", headers=cabecalho)
    assert stripe_falso.cancelados == ["sub_123"]


def test_stripe_webhook_com_assinatura_falsa_e_recusado(cliente, stripe_falso):
    payload, assinatura = evento_assinado(
        "checkout.session.completed", {"id": "cs_x", "object": "checkout.session"}, segredo="whsec_de_um_impostor"
    )
    r = cliente.post("/planos/webhook", content=payload, headers={"Stripe-Signature": assinatura})
    assert r.status_code == 400
    assert cliente.post("/planos/webhook", content=payload).status_code == 400  # sem cabeçalho


def test_webhook_no_modo_simulado_da_400(cliente):
    assert cliente.post("/planos/webhook", content=b"{}").status_code == 400
