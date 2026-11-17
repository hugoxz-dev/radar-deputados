"""Linha de comando do ETL.

Exemplos (dentro do container: `docker compose exec api python -m app.etl ...`):

    python -m app.etl carga-inicial                      # últimos 12 meses, todos os deputados
    python -m app.etl carga-inicial --meses 3 --uf MA    # recorte menor, bom para testar
    python -m app.etl carga-inicial --limite-deputados 20
    python -m app.etl atualizar                          # só mês atual e anterior
    python -m app.etl recalcular-alertas                 # gastos fora do padrão (+ e-mails)
    python -m app.etl ciclo-diario                       # tudo, na ordem (o que o agendador roda)
    python -m app.etl gerar-resumos                      # resumos (LLM_PROVEDOR no .env)
    python -m app.etl gerar-resumos --deputado 204379 --forcar
"""

import argparse
import logging
import sys

from app.etl import rotinas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.etl", description="ETL do Radar dos Deputados")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_carga = sub.add_parser("carga-inicial", help="deputados + despesas dos últimos N meses")
    p_carga.add_argument("--meses", type=int, help="quantos meses para trás (padrão: ETL_MESES_CARGA_INICIAL)")
    p_carga.add_argument("--limite-deputados", type=int, help="processa só os N primeiros (para testes)")
    p_carga.add_argument("--uf", help="processa só os deputados de uma UF (ex.: MA)")

    sub.add_parser("atualizar", help="atualização incremental (mês atual e anterior)")
    p_alertas = sub.add_parser("recalcular-alertas", help="recalcula os gastos fora do padrão e avisa os inscritos")
    p_alertas.add_argument("--sem-notificar", action="store_true", help="não envia e-mails")
    sub.add_parser("ciclo-diario", help="atualizar + recalcular-alertas + gerar-resumos (o que o agendador roda)")
    p_resumos = sub.add_parser("gerar-resumos", help="gera os resumos em linguagem simples (LLM ou template)")
    p_resumos.add_argument("--limite", type=int, help="gera só N resumos (para testar)")
    p_resumos.add_argument("--deputado", type=int, help="gera só o resumo deste deputado (id da Câmara)")
    p_resumos.add_argument("--forcar", action="store_true", help="gera de novo mesmo quem já tem resumo")

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # não logar cada requisição

    if args.comando == "carga-inicial":
        rotinas.carga_inicial(meses=args.meses, limite_deputados=args.limite_deputados, uf=args.uf)
    elif args.comando == "atualizar":
        rotinas.atualizar()
    elif args.comando == "recalcular-alertas":
        rotinas.recalcular_alertas(notificar=not args.sem_notificar)
    elif args.comando == "ciclo-diario":
        rotinas.ciclo_diario()
    elif args.comando == "gerar-resumos":
        rotinas.gerar_resumos(limite=args.limite, deputado_id=args.deputado, forcar=args.forcar)
    else:
        print(f"'{args.comando}' ainda não foi implementado (próximas fases).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
