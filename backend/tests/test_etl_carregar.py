"""Testes da carga no banco: idempotência e sincronização.

Usam a fixture `db` (transação desfeita no fim), então não sujam o banco.
"""

from decimal import Decimal

from sqlalchemy import func, select

from app.etl.carregar import sincronizar_despesas, upsert_deputados
from app.etl.transformar import transformar_deputado, transformar_despesas
from app.models import Despesa, Fornecedor
from tests.dados_exemplo import ID_DEPUTADO_TESTE, deputado_api, despesa_api

PERIODOS = [(2026, 9)]


def _preparar_deputado(db):
    upsert_deputados(db, [transformar_deputado(deputado_api(), 57, True)])


def _despesas_do_deputado(db):
    return db.scalars(select(Despesa).where(Despesa.deputado_id == ID_DEPUTADO_TESTE)).all()


def test_rodar_duas_vezes_nao_duplica(db):
    _preparar_deputado(db)
    brutas = [despesa_api(codDocumento="1"), despesa_api(codDocumento="2", valorDocumento=80.0)]

    for _ in range(2):
        sincronizar_despesas(db, ID_DEPUTADO_TESTE, PERIODOS, transformar_despesas(brutas, ID_DEPUTADO_TESTE))
        db.flush()

    assert len(_despesas_do_deputado(db)) == 2
    cnpj = "00000000000191"
    assert db.scalar(select(func.count()).select_from(Fornecedor).where(Fornecedor.cnpj_cpf == cnpj)) == 1


def test_correcao_da_camara_atualiza_a_nota_existente(db):
    _preparar_deputado(db)
    sincronizar_despesas(
        db, ID_DEPUTADO_TESTE, PERIODOS, transformar_despesas([despesa_api(valorGlosa=0.0)], ID_DEPUTADO_TESTE)
    )
    db.flush()
    sincronizar_despesas(
        db, ID_DEPUTADO_TESTE, PERIODOS, transformar_despesas([despesa_api(valorGlosa=100.0)], ID_DEPUTADO_TESTE)
    )
    db.flush()
    db.expire_all()

    [nota] = _despesas_do_deputado(db)
    assert nota.valor_glosa == Decimal("100.00")
    assert nota.valor_liquido == Decimal("200.00")


def test_nota_removida_na_api_sai_do_banco(db):
    _preparar_deputado(db)
    a, b = despesa_api(codDocumento="1"), despesa_api(codDocumento="2")
    sincronizar_despesas(db, ID_DEPUTADO_TESTE, PERIODOS, transformar_despesas([a, b], ID_DEPUTADO_TESTE))
    db.flush()
    _, removidas = sincronizar_despesas(db, ID_DEPUTADO_TESTE, PERIODOS, transformar_despesas([a], ID_DEPUTADO_TESTE))
    db.flush()

    assert removidas == 1
    assert [d.cod_documento for d in _despesas_do_deputado(db)] == ["1"]


def test_atualizar_inclui_quem_saiu_mas_tem_despesa_recente(db):
    from app.etl.rotinas import deputados_para_atualizar

    # Suplente que já saiu (em_exercicio=False), mas tem nota em setembro
    upsert_deputados(db, [transformar_deputado(deputado_api(), 57, em_exercicio=False)])
    sincronizar_despesas(db, ID_DEPUTADO_TESTE, PERIODOS, transformar_despesas([despesa_api()], ID_DEPUTADO_TESTE))
    db.flush()

    assert ID_DEPUTADO_TESTE in deputados_para_atualizar(db, desde=(2026, 9))
    assert ID_DEPUTADO_TESTE not in deputados_para_atualizar(db, desde=(2026, 10))


def test_sincronizar_nao_mexe_em_outros_meses(db):
    _preparar_deputado(db)
    agosto = despesa_api(mes=8, codDocumento="ago")
    sincronizar_despesas(db, ID_DEPUTADO_TESTE, [(2026, 8)], transformar_despesas([agosto], ID_DEPUTADO_TESTE))
    db.flush()
    # Atualiza só setembro, que veio vazio: agosto precisa continuar lá
    sincronizar_despesas(db, ID_DEPUTADO_TESTE, [(2026, 9)], [])
    db.flush()
    assert [d.cod_documento for d in _despesas_do_deputado(db)] == ["ago"]
