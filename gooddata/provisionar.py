"""Cria ou atualiza o workspace GoodData a partir do código.

    python -m gooddata.provisionar --validar     # só valida LDM + MAQL localmente, sem rede
    python -m gooddata.provisionar               # aplica no GoodData Cloud

Variáveis (.env):
    GOODDATA_HOST           https://<sua-org>.cloud.gooddata.com
    GOODDATA_TOKEN          token de API (Settings > API tokens)
    GOODDATA_WORKSPACE      id do workspace (padrão: museus_br)
    GD_DESTINO              motherduck | postgres
    MOTHERDUCK_TOKEN / MOTHERDUCK_DATABASE   (se motherduck)
    GD_PG_URL                                (se postgres)

Ordem: fonte de dados -> workspace -> LDM -> métricas. Cada passo é
idempotente (create_or_update / put declarativo). O layout aplicado é salvo
em gooddata/layout/ para revisão em PR.

Dashboards: são montados depois, pelo servidor MCP do GoodData (ver
docs/gooddata.md) e exportados para gooddata/layout/ com --exportar.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv

from gooddata.carregar_destino import SCHEMA_DESTINO
from gooddata.modelo_logico import ids_validos, ldm

RAIZ = Path(__file__).resolve().parent.parent
LAYOUT = Path(__file__).resolve().parent / "layout"
DATA_SOURCE_ID = "museus_br"


def metricas() -> list[dict]:
    return yaml.safe_load((Path(__file__).parent / "metricas.yaml").read_text(encoding="utf-8"))["metricas"]


def validar_maql() -> list[str]:
    """Checa toda referência {fact/...}, {attribute/...}, {label/...}, {metric/...} das métricas."""
    validos = ids_validos()
    ids_metricas = {m["id"] for m in metricas()}
    erros = []
    for m in metricas():
        for ref in re.findall(r"\{([a-z]+/[^}]+)\}", m["maql"]):
            tipo, alvo = ref.split("/", 1)
            if tipo == "metric":
                if alvo not in ids_metricas:
                    erros.append(f"{m['id']}: métrica inexistente {ref}")
            elif ref not in validos:
                erros.append(f"{m['id']}: referência inexistente {ref}")
    return erros


def modelo_analitico() -> dict:
    return {
        "analytics": {
            "metrics": [
                {
                    "id": m["id"],
                    "title": m["titulo"],
                    "content": {"format": m["formato"], "maql": " ".join(m["maql"].split())},
                    "tags": ["core"] if m.get("core") else [],
                }
                for m in metricas()
            ],
        }
    }


def _fonte_de_dados():
    from gooddata_sdk import BasicCredentials, CatalogDataSourceMotherDuck, CatalogDataSourcePostgres
    from gooddata_sdk.catalog.entity import TokenCredentials

    destino = os.environ.get("GD_DESTINO", "motherduck")
    if destino == "motherduck":
        banco = os.environ.get("MOTHERDUCK_DATABASE", "museus_br")
        return CatalogDataSourceMotherDuck(
            id=DATA_SOURCE_ID,
            name="Museus do Brasil (MotherDuck)",
            schema=SCHEMA_DESTINO,
            url=f"jdbc:duckdb:md:{banco}",
            credentials=TokenCredentials(token=os.environ["MOTHERDUCK_TOKEN"]),
        )
    u = urlparse(os.environ["GD_PG_URL"])
    return CatalogDataSourcePostgres(
        id=DATA_SOURCE_ID,
        name="Museus do Brasil (PostgreSQL)",
        schema=SCHEMA_DESTINO,
        url=f"jdbc:postgresql://{u.hostname}:{u.port or 5432}{u.path}",
        credentials=BasicCredentials(username=u.username, password=u.password),
    )


def aplicar() -> None:
    from gooddata_sdk import CatalogDeclarativeAnalytics, CatalogWorkspace, GoodDataSdk

    sdk = GoodDataSdk.create(os.environ["GOODDATA_HOST"], os.environ["GOODDATA_TOKEN"])
    workspace = os.environ.get("GOODDATA_WORKSPACE", "museus_br")

    sdk.catalog_data_source.create_or_update_data_source(_fonte_de_dados())
    teste = sdk.catalog_data_source.test_data_sources_connection(
        [sdk.catalog_data_source.get_data_source(DATA_SOURCE_ID)]
    )
    print("conexão:", teste)

    sdk.catalog_workspace.create_or_update(CatalogWorkspace(workspace_id=workspace, name="Museus do Brasil"))
    sdk.catalog_workspace_content.put_declarative_ldm(workspace, ldm(DATA_SOURCE_ID, SCHEMA_DESTINO))
    sdk.catalog_workspace_content.put_declarative_analytics_model(
        workspace, CatalogDeclarativeAnalytics.from_dict(modelo_analitico())
    )
    exportar(sdk, workspace)
    print(f"workspace {workspace} provisionado em {os.environ['GOODDATA_HOST']}")


def exportar(sdk=None, workspace: str | None = None) -> None:
    """Salva o estado atual do workspace (inclusive dashboards criados via MCP) em gooddata/layout/."""
    from gooddata_sdk import GoodDataSdk

    sdk = sdk or GoodDataSdk.create(os.environ["GOODDATA_HOST"], os.environ["GOODDATA_TOKEN"])
    workspace = workspace or os.environ.get("GOODDATA_WORKSPACE", "museus_br")
    LAYOUT.mkdir(parents=True, exist_ok=True)
    (LAYOUT / "ldm.json").write_text(
        json.dumps(
            sdk.catalog_workspace_content.get_declarative_ldm(workspace).to_dict(), indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    (LAYOUT / "analytics_model.json").write_text(
        json.dumps(
            sdk.catalog_workspace_content.get_declarative_analytics_model(workspace).to_dict(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print("layout exportado para", LAYOUT.relative_to(RAIZ))


def main() -> int:
    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(prog="gooddata.provisionar")
    p.add_argument("--validar", action="store_true", help="só valida LDM e MAQL, sem chamar a API")
    p.add_argument("--exportar", action="store_true", help="só exporta o layout atual do workspace")
    args = p.parse_args()

    erros = validar_maql()
    if erros:
        print("\n".join(erros))
        return 1
    modelo = ldm(DATA_SOURCE_ID, SCHEMA_DESTINO)
    print(f"LDM ok: {len(modelo.ldm.datasets)} datasets; {len(metricas())} métricas com referências válidas")
    if args.validar:
        LAYOUT.mkdir(parents=True, exist_ok=True)
        (LAYOUT / "ldm.esperado.json").write_text(
            json.dumps(modelo.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (LAYOUT / "analytics_model.esperado.json").write_text(
            json.dumps(modelo_analitico(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return 0
    if args.exportar:
        exportar()
        return 0
    aplicar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
