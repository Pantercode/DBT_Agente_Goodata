"""Camada de serving: exporta `publicado` para Parquet + um catálogo em JSON.

Por que existe: o painel roda na Vercel (função serverless, sem disco
persistente e sem acesso ao warehouse local). Ele precisa de um snapshot
pequeno, imutável e versionado junto do código. Parquet comprimido com zstd
dá ~2 MB para o projeto inteiro e o DuckDB lê direto, em memória.

O catálogo (catalogo.json) é a versão enxuta do manifest do dbt: descrição de
cada tabela e coluna, linhagem e métricas. É o que o agente de IA usa para
saber o que existe antes de escrever SQL, sem precisar do dbt instalado.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
WAREHOUSE = RAIZ / "data" / "warehouse" / "museus.duckdb"
SERVING = RAIZ / "data" / "serving"
TARGET = RAIZ / "dbt" / "target"


def _exportar_tabelas(con: duckdb.DuckDBPyConnection) -> list[Path]:
    tabelas = [
        r[0]
        for r in con.sql(
            "select table_name from information_schema.tables where table_schema = 'publicado' order by 1"
        ).fetchall()
    ]
    if not tabelas:
        raise RuntimeError("schema `publicado` vazio: rode o pipeline completo antes de exportar")
    saida = []
    for t in tabelas:
        destino = SERVING / f"{t}.parquet"
        con.sql(f"copy publicado.{t} to '{destino.as_posix()}' (format parquet, compression zstd)")
        saida.append(destino)

    # Histórico de testes: só as últimas 30 execuções de build, para a aba Qualidade.
    destino = SERVING / "qualidade_testes.parquet"
    con.sql(f"""
        copy (
            with execucoes as (
                select invocation_id, max(executado_em) as executado_em
                from observabilidade.resultados
                where comando = 'build'
                group by 1
                order by 2 desc
                limit 30
            )
            select r.invocation_id, r.executado_em, r.tipo, r.nome, r.modelo_alvo, r.status,
                   r.severidade, r.bloqueante, r.falhas, r.tempo_s
            from observabilidade.resultados r
            join execucoes e using (invocation_id)
        ) to '{destino.as_posix()}' (format parquet, compression zstd)
    """)
    saida.append(destino)
    return saida


def _catalogo() -> dict:
    manifest = json.loads((TARGET / "manifest.json").read_text(encoding="utf-8"))
    catalog_path = TARGET / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {"nodes": {}}

    modelos = {}
    for uid, no in manifest["nodes"].items():
        if no["resource_type"] != "model" or not no["config"].get("meta", {}).get("publicar"):
            continue
        tipos = {c.lower(): v["type"] for c, v in catalog["nodes"].get(uid, {}).get("columns", {}).items()}
        modelos[no["name"]] = {
            "tabela": f"publicado.{no['name']}",
            "descricao": " ".join(no["description"].split()),
            "camada": no["fqn"][1] if len(no["fqn"]) > 2 else "",
            "materializacao": no["config"]["materialized"],
            "depende_de": [d.split(".")[-1] for d in no["depends_on"]["nodes"]],
            "colunas": {
                nome: {"tipo": tipos.get(nome.lower()), "descricao": " ".join((c.get("description") or "").split())}
                for nome, c in no["columns"].items()
            }
            | {
                nome: {"tipo": tipo, "descricao": ""}
                for nome, tipo in tipos.items()
                if nome not in {k.lower() for k in no["columns"]}
            },
            "testes": sorted(
                {
                    t["test_metadata"]["name"]
                    for t in manifest["nodes"].values()
                    if t["resource_type"] == "test" and uid in t["depends_on"]["nodes"] and t.get("test_metadata")
                }
            ),
        }

    metricas = {
        m["name"]: {"rotulo": m["label"], "descricao": m.get("description", ""), "tipo": m["type"]}
        for m in manifest.get("metrics", {}).values()
    }
    docs = {
        d["name"]: d["block_contents"].strip()
        for d in manifest.get("docs", {}).values()
        if d["package_name"] == "museus_br" and d["name"] != "__overview__"
    }
    return {
        "gerado_em": manifest["metadata"]["generated_at"],
        "modelos": modelos,
        "metricas": metricas,
        "definicoes": docs,
    }


def exportar() -> list[Path]:
    SERVING.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        arquivos = _exportar_tabelas(con)
    destino = SERVING / "catalogo.json"
    destino.write_text(json.dumps(_catalogo(), ensure_ascii=False, indent=1), encoding="utf-8")
    arquivos.append(destino)
    return arquivos


if __name__ == "__main__":
    for a in exportar():
        print(a.relative_to(RAIZ), a.stat().st_size)
