"""Registro de cada execução do ETL na tabela execucoes_etl."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import func

from app.db import SessionLocal
from app.models import ExecucaoETL

log = logging.getLogger(__name__)


@dataclass
class Progresso:
    """O que a rotina vai acumulando durante a execução."""

    registros: int = 0
    avisos: list[str] = field(default_factory=list)


@contextmanager
def registrar_execucao(tipo: str) -> Iterator[Progresso]:
    """Uso:
        with registrar_execucao("atualizar") as progresso:
            ...
            progresso.registros += 10

    Grava "rodando" no início e "sucesso"/"erro" no fim, com sessão própria:
    assim o registro sobrevive mesmo se a rotina der rollback por causa de um erro.
    """
    with SessionLocal() as db:
        execucao = ExecucaoETL(tipo=tipo, status="rodando")
        db.add(execucao)
        db.commit()
        id_execucao = execucao.id
    log.info("Execução #%d (%s) iniciada", id_execucao, tipo)

    progresso = Progresso()
    status, erro = "sucesso", None
    try:
        yield progresso
    except BaseException as excecao:  # inclui Ctrl+C, para não ficar "rodando" para sempre
        status, erro = "erro", f"{type(excecao).__name__}: {excecao}"
        raise
    finally:
        if progresso.avisos:
            # Falhas parciais (ex.: um deputado que não baixou) não derrubam a execução,
            # mas ficam registradas.
            resumo = f"{len(progresso.avisos)} aviso(s): " + "; ".join(progresso.avisos[:20])
            erro = f"{erro}\n{resumo}" if erro else resumo
        with SessionLocal() as db:
            execucao = db.get(ExecucaoETL, id_execucao)
            execucao.status = status
            execucao.fim = func.now()
            execucao.registros = progresso.registros
            execucao.erro = erro
            db.commit()
        log.info("Execução #%d terminou: %s, %d registros", id_execucao, status, progresso.registros)
