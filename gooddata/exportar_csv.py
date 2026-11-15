"""Plano B para o GoodData sem token de API: exporta as tabelas do modelo em CSV.

    python -m gooddata.exportar_csv

Gera gooddata/csv/gd_municipio.csv e gd_museu.csv a partir de `publicado`,
para subir pela interface ("Conectar dados" > upload de arquivo). As métricas
saem prontas para colar em gooddata/csv/metricas_maql.md.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from gooddata.carregar_destino import TABELAS, WAREHOUSE
from gooddata.provisionar import metricas

DESTINO = Path(__file__).resolve().parent / "csv"


def main() -> None:
    DESTINO.mkdir(exist_ok=True)
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        for tabela in TABELAS:
            arquivo = DESTINO / f"{tabela}.csv"
            con.execute(f"copy publicado.{tabela} to '{arquivo.as_posix()}' (header, delimiter ',')")
            n = con.execute(f"select count(*) from publicado.{tabela}").fetchone()[0]
            print(f"{arquivo.name}: {n} linhas")

    linhas = [
        "# Métricas para colar no GoodData",
        "",
        "Em *Analisar > Métricas > Criar métrica*, cole o MAQL de cada uma. Os nomes entre",
        "chaves (`{fact/museu.is_aberto}`) precisam bater com os IDs dos campos depois do",
        "upload: confira em *Modelo de dados* e ajuste se o GoodData tiver gerado outro ID.",
        "Crie na ordem desta lista (algumas usam métricas anteriores).",
        "",
    ]
    for m in metricas():
        linhas += [
            f"## {m['titulo']}",
            f"ID: `{m['id']}` · formato `{m['formato']}`",
            "",
            "```",
            " ".join(m["maql"].split()),
            "```",
            "",
        ]
    (DESTINO / "metricas_maql.md").write_text("\n".join(linhas), encoding="utf-8")
    print("metricas_maql.md")


if __name__ == "__main__":
    main()
