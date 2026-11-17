"""Etapa L do ETL: grava no PostgreSQL de forma idempotente.

Idempotente = rodar duas vezes dá o mesmo resultado que rodar uma.
Usamos o "upsert" do Postgres (INSERT ... ON CONFLICT DO UPDATE):
- se a linha não existe (pela chave única), insere;
- se já existe, atualiza os campos que podem mudar.
"""

import pandas as pd
from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.etl.transformar import slugify
from app.models import Alerta, Categoria, Deputado, Despesa, Fornecedor
from app.services.anomalias import AlertaCalculado
from app.services.categorias import nome_categoria


def upsert_deputados(db: Session, linhas: list[dict]) -> int:
    if not linhas:
        return 0
    stmt = insert(Deputado).values(linhas)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Deputado.id],
        set_={
            "nome": stmt.excluded.nome,
            "partido": stmt.excluded.partido,
            "uf": stmt.excluded.uf,
            "url_foto": stmt.excluded.url_foto,
            "email": stmt.excluded.email,
            "legislatura": stmt.excluded.legislatura,
            "em_exercicio": stmt.excluded.em_exercicio,
            "atualizado_em": func.now(),
        },
    )
    db.execute(stmt)
    return len(linhas)


def ids_sem_nome_civil(db: Session) -> list[int]:
    return list(db.scalars(select(Deputado.id).where(Deputado.nome_civil.is_(None))))


def gravar_nomes_civis(db: Session, nomes: dict[int, str]) -> None:
    for id_deputado, nome_civil in nomes.items():
        if nome_civil:
            db.get(Deputado, id_deputado).nome_civil = nome_civil


def garantir_categorias(db: Session, descricoes: set[str]) -> dict[str, int]:
    """Cria as categorias que ainda não existem e devolve {descricao: id}."""
    if descricoes:
        stmt = insert(Categoria).values([{"descricao": d, "slug": slugify(d)} for d in sorted(descricoes)])
        db.execute(stmt.on_conflict_do_nothing(index_elements=[Categoria.descricao]))
    linhas = db.execute(select(Categoria.descricao, Categoria.id).where(Categoria.descricao.in_(descricoes)))
    return dict(linhas.all())


def garantir_fornecedores(db: Session, nomes_por_cnpj: dict[str, str]) -> dict[str, int]:
    """Cria/atualiza os fornecedores e devolve {cnpj_cpf: id}.

    O nome é atualizado para o mais recente: o mesmo CNPJ às vezes aparece
    com grafias diferentes, e assim ficamos com uma só.
    """
    if not nomes_por_cnpj:
        return {}
    # Um mesmo CNPJ não pode aparecer duas vezes no mesmo INSERT ... ON CONFLICT
    # (o Postgres recusa); o dicionário já garante isso.
    valores = [{"cnpj_cpf": c, "nome": n[:255]} for c, n in sorted(nomes_por_cnpj.items())]
    stmt = insert(Fornecedor).values(valores)
    db.execute(stmt.on_conflict_do_update(index_elements=[Fornecedor.cnpj_cpf], set_={"nome": stmt.excluded.nome}))
    linhas = db.execute(
        select(Fornecedor.cnpj_cpf, Fornecedor.id).where(Fornecedor.cnpj_cpf.in_(nomes_por_cnpj.keys()))
    )
    return dict(linhas.all())


# Campos que a Câmara pode corrigir numa nota já publicada
CAMPOS_ATUALIZAVEIS = ("valor_glosa", "valor_liquido", "url_documento", "tipo_documento", "fornecedor_id")


def sincronizar_despesas(
    db: Session, deputado_id: int, periodos: list[tuple[int, int]], linhas: list[dict]
) -> tuple[int, int]:
    """Deixa as despesas do deputado nos períodos exatamente iguais às da API.

    1. upsert de cada nota pelo hash_unico (insere novas, atualiza existentes);
    2. apaga as notas desses períodos que não vieram mais na API
       (a Câmara às vezes corrige ou remove notas).

    Retorna (notas gravadas, notas removidas).
    """
    categorias = garantir_categorias(db, {linha["categoria"] for linha in linhas})
    fornecedores = garantir_fornecedores(
        db, {linha["fornecedor_cnpj"]: linha["fornecedor_nome"] for linha in linhas if linha["fornecedor_cnpj"]}
    )

    valores = []
    for linha in linhas:
        valor = {k: v for k, v in linha.items() if k not in ("categoria", "fornecedor_cnpj", "fornecedor_nome")}
        valor["categoria_id"] = categorias[linha["categoria"]]
        valor["fornecedor_id"] = fornecedores.get(linha["fornecedor_cnpj"]) if linha["fornecedor_cnpj"] else None
        valores.append(valor)

    if valores:
        stmt = insert(Despesa).values(valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Despesa.hash_unico],
            set_={campo: stmt.excluded[campo] for campo in CAMPOS_ATUALIZAVEIS},
        )
        db.execute(stmt)

    hashes_atuais = [v["hash_unico"] for v in valores]
    remover = delete(Despesa).where(
        Despesa.deputado_id == deputado_id,
        tuple_(Despesa.ano, Despesa.mes).in_(periodos),
    )
    if hashes_atuais:
        remover = remover.where(Despesa.hash_unico.not_in(hashes_atuais))
    removidas = db.execute(remover).rowcount
    return len(valores), removidas


# ------------------------------------------------------------------ alertas


def carregar_despesas_para_analise(db: Session) -> pd.DataFrame:
    """Todas as despesas do banco num DataFrame, no formato que services/anomalias.py espera."""
    consulta = (
        select(
            Despesa.id,
            Despesa.deputado_id,
            Deputado.uf,
            Despesa.categoria_id,
            Categoria.slug.label("categoria_slug"),
            Categoria.descricao.label("categoria_descricao"),
            Despesa.fornecedor_id,
            Fornecedor.nome.label("fornecedor_nome"),
            Despesa.ano,
            Despesa.mes,
            Despesa.data_documento,
            Despesa.valor_liquido.label("valor"),
        )
        .join(Deputado, Deputado.id == Despesa.deputado_id)
        .join(Categoria, Categoria.id == Despesa.categoria_id)
        .outerjoin(Fornecedor, Fornecedor.id == Despesa.fornecedor_id)
    )
    df = pd.DataFrame(db.execute(consulta).all())
    if df.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "deputado_id",
                "uf",
                "categoria_id",
                "categoria_slug",
                "categoria_nome",
                "fornecedor_id",
                "fornecedor_nome",
                "ano",
                "mes",
                "data_documento",
                "valor",
            ]
        )
    df["valor"] = df["valor"].astype(float)  # estatística em float; o banco continua com Decimal
    df["categoria_nome"] = [
        nome_categoria(s, d) for s, d in zip(df["categoria_slug"], df["categoria_descricao"], strict=True)
    ]
    return df


def gravar_alertas(db: Session, alertas: list[AlertaCalculado]) -> tuple[list[int], int]:
    """Sincroniza a tabela `alertas` com o resultado do cálculo.

    - alerta com chave nova: INSERT (é um alerta NOVO, a ser notificado);
    - chave já existente: UPDATE dos números e do texto, mantendo `criado_em`
      (assim ele não volta a ser notificado);
    - chave que não apareceu mais (os dados mudaram): DELETE.

    Retorna (ids dos alertas novos, quantidade removida).
    """
    existentes = set(db.scalars(select(Alerta.chave)))
    chaves_atuais = {a.chave for a in alertas}
    linhas = [
        {
            "chave": a.chave,
            "regra": a.regra,
            "deputado_id": a.deputado_id,
            "categoria_id": a.categoria_id,
            "ano": a.ano,
            "mes": a.mes,
            "despesa_id": a.despesa_id,
            "score": a.score,
            "valor_referencia": a.valor_referencia,
            "explicacao": a.explicacao,
        }
        for a in alertas
    ]
    for inicio in range(0, len(linhas), 1000):  # em lotes, para não estourar o limite de parâmetros do SQL
        stmt = insert(Alerta).values(linhas[inicio : inicio + 1000])
        stmt = stmt.on_conflict_do_update(
            index_elements=[Alerta.chave],
            set_={
                c: stmt.excluded[c]
                for c in ("score", "valor_referencia", "explicacao", "despesa_id", "categoria_id", "mes")
            },
        )
        db.execute(stmt)

    obsoletas = existentes - chaves_atuais
    removidas = 0
    if obsoletas:
        removidas = db.execute(delete(Alerta).where(Alerta.chave.in_(obsoletas))).rowcount
    novas = chaves_atuais - existentes
    ids_novos = list(db.scalars(select(Alerta.id).where(Alerta.chave.in_(novas)))) if novas else []
    return ids_novos, removidas
