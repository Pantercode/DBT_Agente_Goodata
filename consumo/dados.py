"""Conexão somente-leitura com os marts publicados.

Os Parquet de data/serving são montados como views em um DuckDB em memória,
no schema `publicado`, com os mesmos nomes do warehouse. Assim o SQL que roda
contra o warehouse local roda igual na Vercel, e o agente não tem como
enxergar staging, intermediate ou auditoria: elas simplesmente não existem
nessa conexão.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
SERVING = RAIZ / "data" / "serving"

_lock = threading.Lock()


@lru_cache(maxsize=1)
def _conexao_base() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("create schema publicado")
    # Tabelas (não views): o serving inteiro tem poucos MB e precisa estar em
    # memória antes de fechar o acesso a arquivos logo abaixo; uma view sobre
    # read_parquet passaria a falhar.
    for arquivo in sorted(SERVING.glob("*.parquet")):
        con.execute(f"create table publicado.{arquivo.stem} as select * from read_parquet('{arquivo.as_posix()}')")
    # Fecha a porta para o disco e para a rede: nenhuma query (do agente,
    # principalmente) consegue ler outro arquivo daqui em diante.
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")
    return con


def cursor() -> duckdb.DuckDBPyConnection:
    """Cursor novo por chamada: o DuckDB não é thread-safe por conexão, cursores são."""
    with _lock:
        return _conexao_base().cursor()


def consultar(sql: str, params: list | None = None) -> list[dict]:
    cur = cursor()
    rel = cur.execute(sql, params or [])
    colunas = [d[0] for d in rel.description]
    return [dict(zip(colunas, linha, strict=True)) for linha in rel.fetchall()]


def tabelas() -> list[str]:
    return [
        r["table_name"]
        for r in consultar(
            "select table_name from information_schema.tables where table_schema = 'publicado' order by 1"
        )
    ]


@lru_cache(maxsize=1)
def catalogo() -> dict:
    caminho = SERVING / "catalogo.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {"modelos": {}, "metricas": {}}


@lru_cache(maxsize=1)
def status_pipeline() -> dict:
    caminho = SERVING / "status_pipeline.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}


@lru_cache(maxsize=1)
def malha_uf() -> dict:
    from consumo.geo import orientar_para_d3

    return orientar_para_d3(json.loads((SERVING / "malha_uf.geojson").read_text(encoding="utf-8")))
