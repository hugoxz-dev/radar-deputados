"""Kit de DEMONSTRAÇÃO. Não faz parte do produto.

    python -m app.demo preparar                 # cria a conta de demonstração (Pro) e inscrições
    python -m app.demo simular-alertas --uf AP  # faz chegar um e-mail de alerta no Mailpit
    python -m app.demo limpar                   # apaga a conta de demonstração

O que este módulo NÃO faz: não cria despesas, deputados ou alertas inventados.
Todos os dados do painel continuam sendo os reais, vindos da API da Câmara.

`simular-alertas` reproduz o que acontece quando chegam notas novas: apaga
alguns alertas REAIS de um estado e roda o recálculo de verdade. As regras
encontram esses mesmos alertas de novo, eles contam como "novos" e os
inscritos recebem o e-mail, exatamente pelo caminho de produção.
"""

import argparse
import logging

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.etl import rotinas
from app.models import Alerta, Deputado, InscricaoAlerta, Usuario
from app.seguranca import gerar_hash_senha
from app.services.pagamentos import PagamentoSimulado

log = logging.getLogger("app.demo")

# Domínio ".invalido" não existe: um e-mail da demonstração nunca chega a uma pessoa real.
# (".local" não serve: o validador de e-mail recusa domínios reservados.)
EMAIL_DEMO = "demo@radar-deputados.invalido"
SENHA_DEMO = "demonstracao123"  # conta só de demonstração, documentada no README
NOME_DEMO = "Conta de Demonstração"


def preparar(uf: str, deputado_id: int | None) -> None:
    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.email == EMAIL_DEMO))
        if usuario is None:
            usuario = Usuario(email=EMAIL_DEMO, nome=NOME_DEMO, senha_hash=gerar_hash_senha(SENHA_DEMO))
            db.add(usuario)
            db.commit()
        if usuario.plano != "pro":
            PagamentoSimulado().assinar(db, usuario)

        if deputado_id is None:
            # Padrão: o deputado do estado com mais alertas (rende uma boa demonstração)
            deputado_id = db.scalar(
                select(Deputado.id)
                .join(Alerta, Alerta.deputado_id == Deputado.id)
                .where(Deputado.uf == uf)
                .group_by(Deputado.id)
                .order_by(func.count(Alerta.id).desc(), Deputado.id)
                .limit(1)
            )
        for tipo, valor in [("uf", uf), ("deputado", str(deputado_id))]:
            if valor and valor != "None":
                existe = db.scalar(
                    select(InscricaoAlerta).where(
                        InscricaoAlerta.usuario_id == usuario.id,
                        InscricaoAlerta.tipo == tipo,
                        InscricaoAlerta.valor == valor,
                    )
                )
                if existe is None:
                    db.add(InscricaoAlerta(usuario_id=usuario.id, tipo=tipo, valor=valor))
        db.commit()

    print(f"\nConta de demonstração pronta (plano Pro, modo simulado):\n  e-mail: {EMAIL_DEMO}\n  senha:  {SENHA_DEMO}")
    print(f"  acompanha: estado {uf} e o deputado {deputado_id}\n")


def simular_alertas(uf: str, quantidade: int) -> None:
    with SessionLocal() as db:
        ids = list(
            db.scalars(
                select(Alerta.id)
                .join(Deputado, Deputado.id == Alerta.deputado_id)
                .where(Deputado.uf == uf)
                .order_by(Alerta.ano.desc(), Alerta.mes.desc().nulls_last(), Alerta.id.desc())
                .limit(quantidade)
            )
        )
        if not ids:
            print(f"Nenhum alerta em {uf}. Rode antes: python -m app.etl recalcular-alertas")
            return
        db.execute(delete(Alerta).where(Alerta.id.in_(ids)))
        db.commit()
    print(f"{len(ids)} alertas reais de {uf} removidos; recalculando (eles voltam como novos e geram e-mail)...")
    novos = rotinas.recalcular_alertas(notificar=True)
    print(f"\n{len(novos)} alerta(s) novo(s). Veja o e-mail em http://localhost:8025\n")


def limpar() -> None:
    with SessionLocal() as db:
        apagados = db.execute(delete(Usuario).where(Usuario.email == EMAIL_DEMO)).rowcount
        db.commit()
    print("Conta de demonstração apagada." if apagados else "Não havia conta de demonstração.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo", description="Kit de demonstração do Radar dos Deputados"
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    p_prep = sub.add_parser("preparar", help="cria a conta Pro de demonstração e as inscrições")
    p_prep.add_argument("--uf", default="AP", help="estado acompanhado (padrão: AP)")
    p_prep.add_argument("--deputado", type=int, help="id do deputado acompanhado (padrão: um do estado)")
    p_sim = sub.add_parser("simular-alertas", help="faz chegar um e-mail de alertas novos no Mailpit")
    p_sim.add_argument("--uf", default="AP")
    p_sim.add_argument("--quantidade", type=int, default=3)
    sub.add_parser("limpar", help="apaga a conta de demonstração")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.comando == "preparar":
        preparar(args.uf.upper(), args.deputado)
    elif args.comando == "simular-alertas":
        simular_alertas(args.uf.upper(), args.quantidade)
    else:
        limpar()


if __name__ == "__main__":
    main()
