"""Testes do agente que não chamam a API: memória, exemplos, sugestões, gráfico."""

import pytest

from agente import ferramentas, memoria
from agente.guarda_sql import validar
from agente.nucleo import separar_sugestoes
from consumo.dados import consultar, tabelas


@pytest.mark.parametrize("exemplo", memoria.exemplos(), ids=lambda e: e["pergunta"][:40])
def test_exemplo_verificado_roda_e_devolve_linhas(exemplo):
    # Exemplo quebrado ensina errado: todo SQL do banco de exemplos tem que rodar hoje.
    v = validar(exemplo["sql"], set(tabelas()))
    assert consultar(v.sql), f"sem linhas: {exemplo['pergunta']}"


@pytest.mark.parametrize(
    ("pergunta", "esperado"),
    [
        ("quantos museus por habitante tem o nordeste", "Quantos museus por 100 mil habitantes tem a região Nordeste?"),
        ("a coleta de ontem deu problema?", "Os dados de hoje são confiáveis? Alguma coleta foi descartada?"),
        ("qual cidade grande não tem museu", "Qual a maior cidade sem nenhum museu ativo?"),
        ("tipologia de acervo mais comum", "Quais tipologias de acervo são mais frequentes?"),
    ],
)
def test_recupera_o_exemplo_certo(pergunta, esperado):
    assert memoria.exemplos_parecidos(pergunta)[0]["pergunta"] == esperado


def test_catalogo_no_prompt_tem_as_tabelas_principais():
    bloco = memoria.bloco_para_prompt("museus na bahia")
    for t in ("agg_cobertura_uf", "obt_museus", "dim_museu", "mart_saude_coleta"):
        assert f"publicado.{t}" in bloco


def test_separa_bloco_de_sugestoes():
    texto = "O Sul lidera.\n\nFonte: agg\n\n---\nPróximas perguntas:\n- Por quê?\n- E o Norte?\n- Quantos fecharam?\n"
    corpo, sugestoes = separar_sugestoes(texto)
    assert corpo.endswith("Fonte: agg")
    assert sugestoes == ["Por quê?", "E o Norte?", "Quantos fecharam?"]


def test_sem_bloco_de_sugestoes_nao_corta_texto():
    assert separar_sugestoes("Resposta simples.\n\nFonte: x") == ("Resposta simples.\n\nFonte: x", [])


def test_grafico_devolve_figura_para_o_usuario_e_resumo_para_o_modelo():
    r = ferramentas.criar_grafico(
        "select uf_sigla, museus_por_100k_hab from agg_cobertura_uf order by 2 limit 5",
        "barras_horizontais",
        "uf_sigla",
        "museus_por_100k_hab",
        "Menor densidade",
    )
    assert "_figura" in r and r["_figura"]["data"][0]["type"] == "bar"
    assert r["linhas_desenhadas"] == 5
    assert "erro" not in r


def test_grafico_recusa_sql_fora_de_publicado():
    r = ferramentas.criar_grafico("select * from auditoria.dim_museu", "barras", "a", "b", "x")
    assert "erro" in r


def test_grafico_recusa_serie_com_categorias_demais():
    r = ferramentas.criar_grafico(
        "select uf_sigla, regiao_sigla, qtd_museus_ativos from agg_cobertura_uf",
        "barras",
        "uf_sigla",
        "qtd_museus_ativos",
        "x",
        serie="uf_sigla",
    )
    assert "erro" in r and "categorias" in r["erro"]
