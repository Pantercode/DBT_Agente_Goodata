"""Fumaça do painel: toda página responde e os números de capa batem com o mart."""

import pytest
from fastapi.testclient import TestClient

from consumo.dados import consultar
from painel.app import app

cliente = TestClient(app)


@pytest.mark.parametrize(
    "rota",
    [
        "/",
        "/territorio",
        "/gestao",
        "/acessibilidade",
        "/qualidade",
        "/agente",
        "/?regiao=NE",
        "/gestao?uf=BA",
        "/territorio?uf=XX",
    ],
)
def test_paginas_respondem(rota):
    r = cliente.get(rota)
    assert r.status_code == 200
    assert "Museus" in r.text


def test_capa_mostra_o_numero_do_mart():
    brasil = consultar("select qtd_museus_ativos from publicado.agg_cobertura_brasil")[0]["qtd_museus_ativos"]
    numero = f"{brasil:,}".replace(",", ".")
    assert numero in cliente.get("/").text


def test_filtro_de_regiao_recalcula_razao_por_numerador_e_denominador():
    from painel.consultas import Filtro, indicadores

    ne = indicadores(Filtro(regiao="NE"))
    ufs = consultar("select qtd_museus_ativos, populacao from publicado.agg_cobertura_uf where regiao_sigla = 'NE'")
    esperado = sum(u["qtd_museus_ativos"] for u in ufs) * 100000 / sum(u["populacao"] for u in ufs)
    assert ne["museus_por_100k_hab"] == pytest.approx(esperado)


def test_saude():
    assert cliente.get("/api/saude").json()["ok"] is True
