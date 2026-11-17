"""Período de análise (intervalo de meses), usado pelas consultas e pelas rotas."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, and_, or_, tuple_


@dataclass(frozen=True)
class Periodo:
    """Intervalo de meses, inclusivo nas duas pontas: de=(2025, 12), ate=(2026, 11)."""

    de: tuple[int, int]
    ate: tuple[int, int]

    @classmethod
    def ultimos_meses(cls, quantidade: int = 12, ate: tuple[int, int] | None = None) -> "Periodo":
        """Os últimos N meses terminando em `ate` (padrão: mês atual). Ex.: 12 -> dez/2025 a nov/2026."""
        if ate is None:
            hoje = date.today()
            ate = (hoje.year, hoje.month)
        indice = ate[0] * 12 + ate[1] - 1 - (quantidade - 1)
        return cls(de=(indice // 12, indice % 12 + 1), ate=ate)

    @property
    def chave(self) -> str:
        """Identificador curto do período, usado em resumos_ia.periodo: "2025-12_2026-11"."""
        r = self.para_resposta()
        return f"{r['de']}_{r['ate']}"

    def filtro(self, coluna_ano, coluna_mes) -> ColumnElement[bool]:
        """WHERE (ano, mes) >= de AND (ano, mes) <= ate. Usa o índice (ano, mes)."""
        par = tuple_(coluna_ano, coluna_mes)
        return and_(par >= tuple_(*self.de), par <= tuple_(*self.ate))

    def filtro_mes_ou_ano(self, coluna_ano, coluna_mes) -> ColumnElement[bool]:
        """Para registros que podem ser de um mês OU do ano inteiro (mes nulo), como os alertas.

        - Com mês: precisa cair dentro do período.
        - Sem mês (anual): basta o ANO se sobrepor ao período. Ex.: um alerta de
          2026 aparece no período dez/2025 a nov/2026.
        """
        return or_(
            and_(coluna_mes.is_not(None), self.filtro(coluna_ano, coluna_mes)),
            and_(coluna_mes.is_(None), coluna_ano.between(self.de[0], self.ate[0])),
        )

    def meses(self) -> list[tuple[int, int]]:
        """Todos os meses do período, em ordem (para preencher meses sem gasto nos gráficos)."""
        resultado = []
        ano, mes = self.de
        while (ano, mes) <= self.ate:
            resultado.append((ano, mes))
            ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
        return resultado

    def para_resposta(self) -> dict[str, str]:
        return {"de": f"{self.de[0]}-{self.de[1]:02d}", "ate": f"{self.ate[0]}-{self.ate[1]:02d}"}
