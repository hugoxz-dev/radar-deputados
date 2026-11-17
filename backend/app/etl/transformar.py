"""Etapa T do ETL: converte o JSON cru da API para o formato das nossas tabelas.

Só funções puras (sem rede, sem banco): fáceis de testar e de explicar.

Peculiaridades da API descobertas na validação com dados reais (nov/2026):

1. `valorLiquido` vem com o SINAL INVERTIDO em ~75% das notas (ex.: documento
   300.00, líquido -300.00), quase sempre nas notas ainda sem `numRessarcimento`.
   O arquivo CSV anual da Câmara traz as mesmas notas com o líquido positivo,
   o que confirma que é um artefato da API. Por isso CALCULAMOS o líquido como
   `valorDocumento - valorGlosa`, que tem o sinal correto em todos os casos,
   inclusive nos créditos legítimos (passagem cancelada: documento negativo).
2. `valorGlosa` pode vir null: tratamos como 0.
3. `codDocumento` é numérico na maioria, mas é um GUID nas passagens do SIGEPA.
4. `dataDocumento` pode vir null e vem com hora ("2026-09-19T19:00:50").
"""

import hashlib
import re
import unicodedata
from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Any

CENTAVO = Decimal("0.01")


def slugify(texto: str) -> str:
    """'COMBUSTÍVEIS E LUBRIFICANTES.' -> 'combustiveis-e-lubrificantes'"""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def so_digitos(valor: str | None) -> str:
    """CNPJ/CPF só com números ('085.324.290/0013-1' -> '0853242900131')."""
    return re.sub(r"\D", "", valor or "")


def para_decimal(valor: Any) -> Decimal:
    """Número da API (float) -> Decimal com 2 casas. Null vira 0.

    Passamos por str() para não herdar a imprecisão do float (ex.: 0.1).
    """
    if valor is None or valor == "":
        return Decimal("0.00")
    return Decimal(str(valor)).quantize(CENTAVO)


def para_data(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def transformar_deputado(raw: dict, legislatura: int, em_exercicio: bool) -> dict:
    return {
        "id": int(raw["id"]),
        "nome": (raw.get("nome") or "").strip(),
        "partido": raw.get("siglaPartido") or "S.PART.",  # notação da própria Câmara para "sem partido"
        "uf": raw.get("siglaUf") or "",
        "url_foto": raw.get("urlFoto"),
        "email": raw.get("email") or None,
        "legislatura": int(raw.get("idLegislatura") or legislatura),
        "em_exercicio": em_exercicio,
    }


def _identidade(raw: dict, deputado_id: int) -> tuple:
    """Campos que identificam uma nota. Ficam de fora os que a Câmara pode
    corrigir depois (glosa, líquido, ressarcimento): se mudarem, a mesma nota
    é ATUALIZADA no banco em vez de virar uma nova."""
    return (
        deputado_id,
        raw.get("ano"),
        raw.get("mes"),
        (raw.get("tipoDespesa") or "").strip(),
        str(raw.get("codDocumento") or ""),
        str(raw.get("numDocumento") or ""),
        so_digitos(raw.get("cnpjCpfFornecedor")),
        (raw.get("dataDocumento") or "")[:10],
        str(para_decimal(raw.get("valorDocumento"))),
        raw.get("parcela") or 0,
    )


def transformar_despesas(lista_raw: list[dict], deputado_id: int) -> list[dict]:
    """Converte as despesas cruas de um deputado em linhas prontas para carregar.

    hash_unico = SHA-256 dos campos de identidade + nº da ocorrência.
    O nº da ocorrência existe porque a Câmara às vezes lista duas notas
    idênticas em tudo (ex.: duas contas de telefone iguais); sem ele, a
    segunda seria descartada como duplicata. Como as duas são idênticas,
    a ordem em que chegam não importa: o resultado é sempre o mesmo.
    """
    vistas: Counter[tuple] = Counter()
    linhas = []
    for raw in lista_raw:
        identidade = _identidade(raw, deputado_id)
        vistas[identidade] += 1
        texto = "|".join(map(str, identidade)) + f"#{vistas[identidade]}"
        hash_unico = hashlib.sha256(texto.encode()).hexdigest()

        valor_documento = para_decimal(raw.get("valorDocumento"))
        valor_glosa = para_decimal(raw.get("valorGlosa"))
        cnpj = so_digitos(raw.get("cnpjCpfFornecedor"))

        linhas.append(
            {
                "deputado_id": deputado_id,
                # Categoria e fornecedor vão como texto; o carregar.py troca pelos ids
                "categoria": (raw.get("tipoDespesa") or "NÃO INFORMADA").strip(),
                "fornecedor_cnpj": cnpj or None,
                # " ".join(split()) junta espaços repetidos ("LTDA  92" -> "LTDA 92")
                "fornecedor_nome": " ".join((raw.get("nomeFornecedor") or "").split()) or "NÃO INFORMADO",
                "ano": int(raw["ano"]),
                "mes": int(raw["mes"]),
                "data_documento": para_data(raw.get("dataDocumento")),
                "tipo_documento": raw.get("tipoDocumento") or None,
                "num_documento": (str(raw.get("numDocumento") or "").strip() or None),
                "valor_documento": valor_documento,
                "valor_glosa": valor_glosa,
                "valor_liquido": valor_documento - valor_glosa,  # ver item 1 no topo do arquivo
                "url_documento": raw.get("urlDocumento") or None,
                "cod_documento": (str(raw.get("codDocumento") or "").strip() or None),
                "hash_unico": hash_unico,
            }
        )
    return linhas
