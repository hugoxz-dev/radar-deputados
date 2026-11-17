"""Agendador: roda o ciclo diário (atualizar -> alertas -> e-mails -> resumos) sozinho.

Roda como um processo separado (serviço `scheduler` no docker-compose), e não
dentro da API. Motivo: a API pode ter vários processos (workers) ou reiniciar
com o hot-reload; dentro dela, o job poderia rodar duplicado ou ser interrompido.

    python -m app.scheduler          # fica rodando e dispara no horário (AGENDA_HORA)
    python -m app.scheduler --agora  # roda o ciclo uma vez, já, e sai (útil na demonstração)
"""

import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.etl.rotinas import ciclo_diario

log = logging.getLogger("app.scheduler")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.scheduler")
    parser.add_argument("--agora", action="store_true", help="roda o ciclo uma vez e sai")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.agora:
        ciclo_diario()
        return

    cfg = get_settings()
    agendador = BlockingScheduler(timezone=cfg.agenda_fuso)
    agendador.add_job(
        ciclo_diario,
        CronTrigger(hour=cfg.agenda_hora, minute=cfg.agenda_minuto, timezone=cfg.agenda_fuso),
        id="ciclo_diario",
        max_instances=1,  # se um ciclo atrasar, o próximo não começa por cima dele
        coalesce=True,  # se o computador ficou desligado, roda uma vez só (não várias acumuladas)
        misfire_grace_time=3600,
    )
    log.info("Agendador no ar: ciclo diário às %02d:%02d (%s).", cfg.agenda_hora, cfg.agenda_minuto, cfg.agenda_fuso)
    agendador.start()  # bloqueia aqui até Ctrl+C / docker stop


if __name__ == "__main__":
    main()
