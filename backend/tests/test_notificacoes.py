"""Testes de inscrições de alerta, notificações por e-mail e do ciclo do agendador.

Dados FICTÍCIOS (UF "ZZ", e-mails @exemplo.invalido), desfeitos pelo rollback.
Nenhum e-mail sai de verdade: o envio é capturado nos testes.
"""

import logging
from decimal import Decimal

import pytest

from app.config import Settings
from app.etl import rotinas
from app.etl.carregar import gravar_alertas
from app.models import Categoria, Deputado, Despesa, InscricaoAlerta, Usuario
from app.services import notificacoes
from app.services.anomalias import AlertaCalculado
from app.services.notificacoes import (
    MAX_ALERTAS_POR_EMAIL,
    casar_alertas_com_inscricoes,
    montar_email,
    notificar_novos_alertas,
)

CFG_CONSOLE = Settings(email_backend="console", frontend_url="http://site.teste")


@pytest.fixture
def mundo(db):
    """2 deputados fictícios (ZZ e YY), uma categoria e três usuários (2 Pro, 1 grátis)."""
    cat = Categoria(descricao="CATEGORIA TESTE NOTIF", slug="categoria-teste-notif")
    dep_zz = Deputado(id=994_001, nome="Deputada ZZ", partido="PTESTE", uf="ZZ", legislatura=57)
    dep_yy = Deputado(id=994_002, nome="Deputado YY", partido="PTESTE", uf="YY", legislatura=57)
    pro_uf = Usuario(email="pro-uf@exemplo.invalido", nome="Pro UF", senha_hash="x", plano="pro")
    pro_dep = Usuario(email="pro-dep@exemplo.invalido", nome="Pro Deputado", senha_hash="x", plano="pro")
    gratis = Usuario(email="gratis@exemplo.invalido", nome="Grátis", senha_hash="x", plano="free")
    db.add_all([cat, dep_zz, dep_yy, pro_uf, pro_dep, gratis])
    db.flush()
    nota = Despesa(
        deputado_id=994_001,
        categoria_id=cat.id,
        ano=2026,
        mes=9,
        valor_documento=Decimal("10"),
        valor_liquido=Decimal("10"),
        hash_unico="teste-notif-1",
    )
    db.add(nota)
    db.add_all(
        [
            InscricaoAlerta(usuario_id=pro_uf.id, tipo="uf", valor="ZZ"),
            InscricaoAlerta(usuario_id=pro_dep.id, tipo="deputado", valor="994001"),
            InscricaoAlerta(usuario_id=pro_dep.id, tipo="categoria", valor="categoria-teste-notif"),  # bate de novo
            InscricaoAlerta(usuario_id=gratis.id, tipo="uf", valor="ZZ"),  # não é Pro: não recebe
        ]
    )
    db.flush()
    return {"cat": cat, "nota": nota, "pro_uf": pro_uf, "pro_dep": pro_dep, "gratis": gratis}


def criar_alertas(db, mundo, quantidade=1, deputado_id=994_001, com_categoria=True) -> list[int]:
    alertas = [
        AlertaCalculado(
            chave=f"teste-notif:{deputado_id}:{i}",
            regra="valor_atipico_categoria_uf",
            deputado_id=deputado_id,
            categoria_id=mundo["cat"].id if com_categoria else None,
            ano=2026,
            mes=9,
            despesa_id=mundo["nota"].id,
            score=5.0,
            valor_referencia=1.0,
            explicacao=f"Valor de teste {i} é 9 vezes a mediana.",
        )
        for i in range(quantidade)
    ]
    # gravar_alertas sincroniza a tabela inteira; aqui só importam os ids novos
    novos, _ = gravar_alertas(db, alertas)
    return novos


# ---------------------------------------------------------- quem recebe o quê


def test_alerta_chega_a_quem_acompanha_a_uf_e_o_deputado(db, mundo):
    ids = criar_alertas(db, mundo)
    por_usuario = casar_alertas_com_inscricoes(db, ids)
    assert set(por_usuario) == {mundo["pro_uf"].id, mundo["pro_dep"].id}
    # pro_dep tem duas inscrições que batem (deputado e categoria): recebe o alerta UMA vez
    assert len(por_usuario[mundo["pro_dep"].id]) == 1


def test_usuario_gratis_e_inscricao_inativa_nao_recebem(db, mundo):
    db.query(InscricaoAlerta).filter_by(usuario_id=mundo["pro_uf"].id).update({"ativo": False})
    ids = criar_alertas(db, mundo)
    assert mundo["gratis"].id not in casar_alertas_com_inscricoes(db, ids)
    assert mundo["pro_uf"].id not in casar_alertas_com_inscricoes(db, ids)


def test_alerta_de_outra_uf_nao_chega(db, mundo):
    # Deputado de YY, sem categoria: nenhuma inscrição (UF ZZ, deputado 994001, categoria) bate
    ids = criar_alertas(db, mundo, deputado_id=994_002, com_categoria=False)
    assert casar_alertas_com_inscricoes(db, ids) == {}


def test_sem_alertas_novos_nao_envia_nada(db, mundo):
    assert notificar_novos_alertas(db, [], CFG_CONSOLE) == 0


# ------------------------------------------------------------------ e-mail


def test_email_tem_explicacao_link_e_aviso(db, mundo, caplog):
    ids = criar_alertas(db, mundo)
    with caplog.at_level(logging.INFO, logger="app.services.notificacoes"):
        enviados = notificar_novos_alertas(db, ids, CFG_CONSOLE)
    assert enviados == 2
    log = caplog.text
    assert "Assunto: Radar dos Deputados: 1 novo gasto fora do padrão" in log
    assert "Valor de teste 0 é 9 vezes a mediana." in log
    assert "http://site.teste/deputados/994001" in log
    assert "não indicam irregularidade" in log


def test_email_longo_e_resumido(mundo):
    alertas = [notificacoes.AlertaParaEmail("Regra", 1, "Dep <b>", f"Explicação {i}", "set/2026") for i in range(25)]
    email = montar_email(mundo["pro_uf"], alertas, "http://site.teste")
    assert email.assunto == "Radar dos Deputados: 25 novos gastos fora do padrão"
    assert email.texto.count("Explicação") == MAX_ALERTAS_POR_EMAIL
    assert "e mais 5" in email.texto
    assert "Dep &lt;b&gt;" in email.html  # nomes escapados no HTML


def test_falha_no_smtp_nao_derruba_o_processo(db, mundo, monkeypatch):
    class SMTPForaDoAr:
        def __init__(self, *args, **kwargs):
            raise OSError("conexão recusada")

    monkeypatch.setattr(notificacoes.smtplib, "SMTP", SMTPForaDoAr)
    ids = criar_alertas(db, mundo)
    assert notificar_novos_alertas(db, ids, Settings(email_backend="smtp")) == 0  # registra erro e segue


# -------------------------------------------------------------- rotas /me/inscricoes


def cadastrar_pro(cliente) -> dict:
    r = cliente.post(
        "/auth/cadastro",
        json={"nome": "Pessoa Pro", "email": "pessoa-pro@exemplo.invalido", "senha": "senha-teste-123"},
    )
    cabecalho = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cliente.post("/planos/assinar", headers=cabecalho)
    return cabecalho


def test_inscricoes_exigem_pro(cliente):
    r = cliente.post(
        "/auth/cadastro", json={"nome": "Grátis", "email": "free@exemplo.invalido", "senha": "senha-teste-123"}
    )
    cabecalho = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert cliente.get("/me/inscricoes", headers=cabecalho).status_code == 403
    assert cliente.get("/me/inscricoes").status_code == 401


def test_criar_listar_e_remover_inscricao(cliente, mundo):
    cabecalho = cadastrar_pro(cliente)
    r = cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "uf", "valor": "zz"})
    assert r.status_code == 201
    assert r.json()["valor"] == "ZZ"  # UF normalizada para maiúsculas
    cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "deputado", "valor": "994001"})

    lista = cliente.get("/me/inscricoes", headers=cabecalho).json()
    assert [i["descricao"] for i in lista] == ["Deputados de ZZ", "Deputada ZZ (PTESTE-ZZ)"]

    assert cliente.delete(f"/me/inscricoes/{lista[0]['id']}", headers=cabecalho).status_code == 204
    assert len(cliente.get("/me/inscricoes", headers=cabecalho).json()) == 1


def test_inscricao_repetida_ou_inexistente(cliente, mundo):
    cabecalho = cadastrar_pro(cliente)
    cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "uf", "valor": "ZZ"})
    assert cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "uf", "valor": "ZZ"}).status_code == 409
    assert cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "deputado", "valor": "1"}).status_code == 422
    assert (
        cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "categoria", "valor": "nao-existe"}).status_code
        == 422
    )
    assert cliente.post("/me/inscricoes", headers=cabecalho, json={"tipo": "partido", "valor": "PT"}).status_code == 422


def test_nao_remove_inscricao_de_outra_pessoa(cliente, mundo):
    cabecalho = cadastrar_pro(cliente)
    inscricao_alheia = mundo["pro_uf"].inscricoes[0].id
    assert cliente.delete(f"/me/inscricoes/{inscricao_alheia}", headers=cabecalho).status_code == 404


# ------------------------------------------------------------------ agendador


def test_ciclo_diario_continua_se_uma_etapa_falhar(monkeypatch):
    executadas = []

    def falha():
        raise RuntimeError("API da Câmara fora do ar")

    monkeypatch.setattr(rotinas, "atualizar", falha)
    monkeypatch.setattr(rotinas, "recalcular_alertas", lambda: executadas.append("alertas"))
    monkeypatch.setattr(rotinas, "gerar_resumos", lambda: executadas.append("resumos"))
    rotinas.ciclo_diario()
    assert executadas == ["alertas", "resumos"]
