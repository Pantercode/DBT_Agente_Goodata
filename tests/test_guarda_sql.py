import pytest

from agente.guarda_sql import LIMITE_MAXIMO, LIMITE_PADRAO, SQLRecusado, validar

TABELAS = {"agg_cobertura_uf", "obt_museus"}


def test_select_simples_ganha_schema_e_limit():
    v = validar("select uf_sigla from agg_cobertura_uf", TABELAS)
    assert "publicado.agg_cobertura_uf" in v.sql
    assert v.sql.endswith(f"LIMIT {LIMITE_PADRAO}")


def test_limit_acima_do_teto_e_reduzido():
    v = validar("select * from obt_museus limit 999999", TABELAS)
    assert v.limite == LIMITE_MAXIMO


def test_cte_com_nome_proprio_nao_e_tratada_como_tabela():
    v = validar("with x as (select * from obt_museus) select count(*) from x", TABELAS)
    assert v.tabelas == ("obt_museus",)


def test_struct_e_unnest_passam():
    validar("select gestao.indice, unnest(tipologias_acervo) from obt_museus", TABELAS)


@pytest.mark.parametrize(
    "sql",
    [
        "drop table obt_museus",
        "delete from obt_museus",
        "insert into obt_museus select * from obt_museus",
        "copy obt_museus to 'x.csv'",
        "attach 'outro.duckdb' as o",
        "set enable_external_access = true",
        "select 1; select 2",
        "select * from auditoria.dim_museu",
        "select * from staging.stg_tainacan__museus",
        "select * from read_csv('/etc/passwd')",
        "select * from read_parquet('data/warehouse/*.parquet')",
        "select * from nao_existe",
        "select * from outro_catalogo.publicado.obt_museus",
    ],
)
def test_recusa(sql):
    with pytest.raises(SQLRecusado):
        validar(sql, TABELAS)


def test_mensagem_de_tabela_inexistente_lista_as_opcoes():
    with pytest.raises(SQLRecusado, match="agg_cobertura_uf"):
        validar("select * from museus", TABELAS)
