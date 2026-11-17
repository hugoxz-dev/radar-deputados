"""Notificações por e-mail: avisa os assinantes Pro sobre NOVOS gastos fora do padrão
que batem com as suas inscrições (deputado, UF ou categoria).

Quando roda: logo depois de cada recálculo de alertas (etl/rotinas.py), com a
lista de alertas que acabaram de surgir. Como um alerta só é "novo" uma vez
(chave estável, ver anomalias.py), ninguém recebe o mesmo alerta duas vezes.

Envio (EMAIL_BACKEND no .env):
- console: imprime o e-mail no log (não precisa de servidor);
- smtp: envia por SMTP. No Docker Compose há o Mailpit, uma caixa de entrada
  de teste: os e-mails aparecem em http://localhost:8025 e não saem para a internet.
"""

import logging
import smtplib
from collections import defaultdict
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Alerta, Categoria, Deputado, InscricaoAlerta, Usuario
from app.services.anomalias import MESES, NOMES_REGRAS

log = logging.getLogger(__name__)

MAX_ALERTAS_POR_EMAIL = 20  # o resto vira "e mais N" com link para o site


@dataclass
class AlertaParaEmail:
    regra: str
    deputado_id: int
    deputado: str
    explicacao: str
    quando: str


@dataclass
class Email:
    para: str
    assunto: str
    texto: str
    html: str


# ------------------------------------------------------------- quem recebe o quê


def casar_alertas_com_inscricoes(db: Session, ids_alertas: list[int]) -> dict[int, list[AlertaParaEmail]]:
    """{usuario_id: [alertas]} para os usuários Pro cujas inscrições ativas batem com os alertas.

    Um alerta que bate com mais de uma inscrição do mesmo usuário aparece uma vez só.
    """
    if not ids_alertas:
        return {}
    linhas = db.execute(
        select(Alerta, Deputado, Categoria, InscricaoAlerta.usuario_id)
        .join(Deputado, Deputado.id == Alerta.deputado_id)
        .outerjoin(Categoria, Categoria.id == Alerta.categoria_id)
        .join(
            InscricaoAlerta,
            or_(
                # inscricoes_alerta.valor é texto; o id do deputado é número: cast para comparar
                (InscricaoAlerta.tipo == "deputado") & (InscricaoAlerta.valor == cast(Alerta.deputado_id, String)),
                (InscricaoAlerta.tipo == "uf") & (InscricaoAlerta.valor == Deputado.uf),
                (InscricaoAlerta.tipo == "categoria") & (InscricaoAlerta.valor == Categoria.slug),
            ),
        )
        .join(Usuario, Usuario.id == InscricaoAlerta.usuario_id)
        .where(Alerta.id.in_(ids_alertas), InscricaoAlerta.ativo, Usuario.plano == "pro")
        .order_by(Alerta.ano.desc(), Alerta.mes.desc().nulls_last(), Alerta.id)
    ).all()

    por_usuario: dict[int, dict[int, AlertaParaEmail]] = defaultdict(dict)
    for alerta, deputado, _categoria, usuario_id in linhas:
        por_usuario[usuario_id].setdefault(
            alerta.id,
            AlertaParaEmail(
                regra=NOMES_REGRAS[alerta.regra],
                deputado_id=deputado.id,
                deputado=f"{deputado.nome} ({deputado.partido}-{deputado.uf})",
                explicacao=alerta.explicacao,
                quando=f"{MESES[alerta.mes - 1]}/{alerta.ano}" if alerta.mes else f"ano de {alerta.ano}",
            ),
        )
    return {u: list(alertas.values()) for u, alertas in por_usuario.items()}


# ------------------------------------------------------------------ e-mail


def montar_email(usuario: Usuario, alertas: list[AlertaParaEmail], frontend_url: str) -> Email:
    n = len(alertas)
    assunto = f"Radar dos Deputados: {n} {'novo gasto fora do padrão' if n == 1 else 'novos gastos fora do padrão'}"
    mostrados, restantes = alertas[:MAX_ALERTAS_POR_EMAIL], n - MAX_ALERTAS_POR_EMAIL
    aviso = "Gastos fora do padrão são destaques estatísticos: não indicam irregularidade."
    link_conta = f"{frontend_url}/minha-conta"

    # Versão em texto puro (leitores de e-mail simples e acessibilidade)
    texto = [
        f"Olá, {usuario.nome}.",
        "",
        f"Encontramos {n} {'novo gasto' if n == 1 else 'novos gastos'} fora do padrão no que você acompanha:",
        "",
    ]
    for a in mostrados:
        texto += [
            f"- [{a.regra}] {a.deputado}, {a.quando}",
            f"  {a.explicacao}",
            f"  {frontend_url}/deputados/{a.deputado_id}",
            "",
        ]
    if restantes > 0:
        texto += [f"... e mais {restantes}. Veja todos em {frontend_url}/alertas", ""]
    texto += [aviso, f"Gerenciar inscrições: {link_conta}"]

    # Versão HTML (mesmo conteúdo, com links clicáveis). escape() evita que um nome com "<" quebre o HTML.
    itens = "".join(
        f"<li style='margin-bottom:12px'><strong>{escape(a.regra)}</strong> · "
        f"<a href='{frontend_url}/deputados/{a.deputado_id}'>{escape(a.deputado)}</a> · {escape(a.quando)}<br>"
        f"{escape(a.explicacao)}</li>"
        for a in mostrados
    )
    mais = f"<p>… e mais {restantes}. <a href='{frontend_url}/alertas'>Ver todos</a></p>" if restantes > 0 else ""
    html = (
        f"<div style='font-family:sans-serif;max-width:600px'>"
        f"<h2 style='color:#0f2f5e'>Radar dos Deputados</h2><p>Olá, {escape(usuario.nome)}.</p>"
        f"<p>Encontramos {n} {'novo gasto' if n == 1 else 'novos gastos'} fora do padrão no que você acompanha:</p>"
        f"<ul>{itens}</ul>{mais}<p style='color:#555;font-size:13px'>{aviso}<br>"
        f"<a href='{link_conta}'>Gerenciar inscrições</a></p></div>"
    )
    return Email(para=usuario.email, assunto=assunto, texto="\n".join(texto), html=html)


def enviar(email: Email, cfg: Settings) -> None:
    if cfg.email_backend == "smtp":
        mensagem = EmailMessage()
        mensagem["From"] = cfg.email_remetente
        mensagem["To"] = email.para
        mensagem["Subject"] = email.assunto
        mensagem.set_content(email.texto)
        mensagem.add_alternative(email.html, subtype="html")
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=10) as smtp:
            smtp.send_message(mensagem)
    else:
        log.info("E-MAIL (backend console)\nPara: %s\nAssunto: %s\n\n%s\n", email.para, email.assunto, email.texto)


def notificar_novos_alertas(db: Session, ids_alertas: list[int], cfg: Settings) -> int:
    """Envia um e-mail por usuário com os alertas novos que batem com as inscrições dele.

    Falha no envio para um usuário não impede os outros (e não desfaz o recálculo).
    Retorna quantos e-mails foram enviados.
    """
    por_usuario = casar_alertas_com_inscricoes(db, ids_alertas)
    enviados = 0
    for usuario_id, alertas in por_usuario.items():
        usuario = db.get(Usuario, usuario_id)
        try:
            enviar(montar_email(usuario, alertas, cfg.frontend_url), cfg)
            enviados += 1
        except (OSError, smtplib.SMTPException) as erro:
            log.error("Falha ao enviar e-mail para o usuário %d: %s", usuario_id, erro)
    log.info("Notificações: %d e-mail(s) enviados (%d alertas novos analisados).", enviados, len(ids_alertas))
    return enviados
