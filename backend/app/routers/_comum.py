"""Peças compartilhadas pelas rotas: período e paginação."""

from dataclasses import dataclass
from datetime import date

from fastapi import Depends, HTTPException, Query

from app.models import Usuario
from app.seguranca import usuario_opcional
from app.services.periodo import Periodo

PADRAO_MES = r"^\d{4}-(0[1-9]|1[0-2])$"
MESES_PADRAO = 12


def _ler_mes(texto: str) -> tuple[int, int]:
    ano, mes = texto.split("-")
    return int(ano), int(mes)


def periodo_param(
    de: str | None = Query(
        None,
        pattern=PADRAO_MES,
        description="Mês inicial (AAAA-MM). Padrão: 11 meses antes de `ate`.",
        examples=["2025-12"],
    ),
    ate: str | None = Query(
        None, pattern=PADRAO_MES, description="Mês final (AAAA-MM). Padrão: mês atual.", examples=["2026-11"]
    ),
    usuario: Usuario | None = Depends(usuario_opcional),
) -> Periodo:
    """Dependência do FastAPI: lê ?de=&ate= e devolve um Periodo validado.

    Padrão: os últimos 12 meses, o mesmo recorte da carga inicial do ETL.
    Antes disso, só para o plano Pro ("histórico completo").
    """
    hoje = date.today()
    fim = _ler_mes(ate) if ate else (hoje.year, hoje.month)
    inicio = _ler_mes(de) if de else Periodo.ultimos_meses(MESES_PADRAO, ate=fim).de
    if inicio > fim:
        raise HTTPException(status_code=422, detail="O mês inicial (de) precisa ser anterior ou igual ao final (ate).")
    # Plano grátis: últimos 12 meses. Antes disso é o "histórico completo", recurso do Pro.
    if inicio < Periodo.ultimos_meses(MESES_PADRAO).de and (usuario is None or usuario.plano != "pro"):
        raise HTTPException(
            status_code=403,
            detail="Consultar meses anteriores aos últimos 12 é um recurso do plano Pro (histórico completo).",
        )
    return Periodo(de=inicio, ate=fim)


@dataclass(frozen=True)
class Paginacao:
    pagina: int
    itens: int

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.itens


def paginacao_param(
    pagina: int = Query(1, ge=1, description="Página (começa em 1)"),
    itens: int = Query(20, ge=1, le=100, description="Itens por página (máx. 100)"),
) -> Paginacao:
    return Paginacao(pagina=pagina, itens=itens)
