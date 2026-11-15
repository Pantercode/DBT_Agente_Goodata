"""Copia as tabelas do GoodData de `publicado` para o banco que o GoodData Cloud lê.

O GoodData Cloud não lê um DuckDB local. Dois destinos suportados:

    python -m gooddata.carregar_destino motherduck   # usa MOTHERDUCK_TOKEN
    python -m gooddata.carregar_destino postgres     # usa GD_PG_URL (postgresql://user:pass@host:5432/db)

Nos dois casos as tabelas vão para o schema `museus_gd` e são recriadas a
cada carga (são pequenas: ~10 mil linhas no total). A carga é feita numa
transação: o GoodData nunca vê metade das tabelas atualizadas.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
WAREHOUSE = RAIZ / "data" / "warehouse" / "museus.duckdb"
SCHEMA_DESTINO = "museus_gd"
TABELAS = ("gd_municipio", "gd_museu")


def carregar(destino: str) -> None:
    load_dotenv(RAIZ / ".env")
    con = duckdb.connect()
    con.execute(f"attach '{WAREHOUSE.as_posix()}' as wh (read_only)")

    if destino == "motherduck":
        if not os.environ.get("MOTHERDUCK_TOKEN"):
            raise SystemExit("Defina MOTHERDUCK_TOKEN no .env")
        banco = os.environ.get("MOTHERDUCK_DATABASE", "museus_br")
        con.execute("install motherduck; load motherduck")
        con.execute("attach 'md:' as md")
        con.execute(f"create database if not exists md.{banco}")
        alvo = f"md_{banco}"
        con.execute(f"attach 'md:{banco}' as {alvo}")
    elif destino == "postgres":
        url = os.environ.get("GD_PG_URL")
        if not url:
            raise SystemExit("Defina GD_PG_URL no .env (postgresql://usuario:senha@host:5432/banco)")
        con.execute("install postgres; load postgres")
        alvo = "pg"
        con.execute(f"attach '{url}' as {alvo} (type postgres)")
    else:
        raise SystemExit(f"destino desconhecido: {destino}")

    con.execute(f"create schema if not exists {alvo}.{SCHEMA_DESTINO}")
    con.execute("begin transaction")
    for tabela in TABELAS:
        con.execute(f"create or replace table {alvo}.{SCHEMA_DESTINO}.{tabela} as select * from wh.publicado.{tabela}")
        n = con.execute(f"select count(*) from {alvo}.{SCHEMA_DESTINO}.{tabela}").fetchone()[0]
        print(f"{tabela}: {n} linhas -> {destino}.{SCHEMA_DESTINO}")
    con.execute("commit")


if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="gooddata.carregar_destino")
    p.add_argument("destino", choices=["motherduck", "postgres"])
    carregar(p.parse_args().destino)
