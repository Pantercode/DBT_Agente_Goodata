"""Dashboard "Museus do Brasil" no GoodData, declarado em código e publicado pelo MCP.

    python -m gooddata.dashboard            # cria/atualiza visualizações, filtros e o dashboard
    python -m gooddata.dashboard --validar  # só executa cada visualização (via MCP) e mostra os números

Cada visualização é uma consulta sobre as métricas de gooddata/metricas.yaml e
os atributos de gooddata/modelo_logico.py. Nenhuma regra de negócio mora aqui.

Publicação: objeto novo vai pelo servidor MCP do GoodData
(createEntityVisualizationObjects, createEntityFilterContexts,
createEntityAnalyticalDashboards). Objeto que já existe é atualizado pela API
REST (PUT), porque o MCP não tem ferramenta de atualização. Rodar de novo não
duplica nada.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import ClassVar

import httpx

from gooddata.mcp_cliente import ClienteMCP

DASHBOARD_ID = "museus_do_brasil"
FILTROS_ID = "museus_do_brasil_filtros"


# ---------------------------------------------------------------- blocos


def _medida(metrica: str, titulo: str | None = None) -> dict:
    m = {
        "measure": {
            "localIdentifier": f"m_{metrica}",
            "definition": {
                "measureDefinition": {"item": {"identifier": {"id": metrica, "type": "metric"}}, "filters": []}
            },
        }
    }
    if titulo:
        m["measure"]["title"] = titulo
    return m


def _atributo(label: str) -> dict:
    return {
        "attribute": {
            "localIdentifier": f"a_{label.replace('.', '_')}",
            "displayForm": {"identifier": {"id": label, "type": "label"}},
        }
    }


def _ordenar_por(metrica: str, direcao: str = "desc") -> list[dict]:
    return [
        {
            "measureSortItem": {
                "direction": direcao,
                "locators": [{"measureLocatorItem": {"measureIdentifier": f"m_{metrica}"}}],
            }
        }
    ]


def _viz(
    id_: str,
    titulo: str,
    tipo: str,
    medidas: list,
    por: list | None = None,
    pilha: list | None = None,
    ordenar: list | None = None,
    descricao: str = "",
    propriedades: dict | None = None,
) -> dict:
    """tipo = visualizationUrl do GoodData.UI: headline, bar, column, table, ..."""
    buckets = [{"localIdentifier": "measures", "items": medidas}]
    if por:
        buckets.append({"localIdentifier": "attribute" if tipo == "table" else "view", "items": por})
    if pilha:
        buckets.append({"localIdentifier": "stack", "items": pilha})
    return {
        "id": id_,
        "title": titulo,
        "description": descricao,
        "content": {
            "buckets": buckets,
            "filters": [],
            "sorts": ordenar or [],
            "properties": {"controls": propriedades or {}},
            "visualizationUrl": f"local:{tipo}",
            "version": "2",
        },
    }


UF = "municipio.uf_sigla"
REGIAO = "municipio.regiao_nome"

VISUALIZACOES = [
    # capa: os quatro números que aparecem no topo do painel em Python
    _viz("kpi_museus_ativos", "Museus ativos", "headline", [_medida("museus_ativos")]),
    _viz("kpi_museus_100k", "Museus por 100 mil habitantes", "headline", [_medida("museus_por_100k_hab")]),
    _viz("kpi_municipios_com_museu", "Municípios com museu", "headline", [_medida("pct_municipios_com_museu")]),
    _viz("kpi_pop_sem_museu", "População em cidade sem museu", "headline", [_medida("pct_populacao_sem_museu")]),
    # território
    _viz(
        "uf_museus_100k",
        "Museus ativos por 100 mil habitantes, por UF",
        "bar",
        [_medida("museus_por_100k_hab", "Museus por 100 mil hab.")],
        [_atributo(UF)],
        ordenar=_ordenar_por("museus_por_100k_hab"),
        descricao="Razão recalculada pelo MAQL (museus ativos × 100.000 / população), igual ao painel.",
    ),
    _viz(
        "regiao_pop_sem_museu",
        "População em cidade sem museu, por região",
        "column",
        [_medida("pct_populacao_sem_museu", "% da população sem museu")],
        [_atributo(REGIAO)],
        ordenar=_ordenar_por("pct_populacao_sem_museu"),
    ),
    _viz(
        "porte_cobertura",
        "Municípios por porte e cobertura museal",
        "column",
        [_medida("qtd_municipios")],
        [_atributo("municipio.faixa_populacional")],
        pilha=[_atributo("municipio.classe_cobertura")],
        propriedades={"stackMeasuresToPercent": True},
        descricao="Proporção de municípios de cada porte (Censo 2022) por classe de cobertura.",
    ),
    # gestão
    _viz(
        "gestao_por_natureza",
        "Gestão por natureza administrativa",
        "table",
        [
            _medida("museus_ativos"),
            _medida("indice_gestao_medio", "Índice de gestão (0-100)"),
            _medida("pct_plano_museologico", "% com plano museológico"),
        ],
        [_atributo("museu.natureza_administrativa")],
        ordenar=_ordenar_por("museus_ativos"),
    ),
    _viz(
        "faixa_gestao",
        "Museus ativos por faixa do índice de gestão",
        "column",
        [_medida("museus_ativos")],
        [_atributo("museu.faixa_gestao")],
        pilha=[_atributo("museu.natureza_administrativa")],
    ),
    # acessibilidade
    _viz(
        "tipo_sem_acessibilidade",
        "Museus sem nenhum recurso de acessibilidade, por tipo",
        "bar",
        [_medida("pct_museus_sem_acessibilidade", "% sem acessibilidade")],
        [_atributo("museu.tipo_museu")],
        ordenar=_ordenar_por("pct_museus_sem_acessibilidade"),
    ),
]


def _item(viz_id: str, titulo: str, largura: int, altura: int, n: int) -> dict:
    return {
        "type": "IDashboardLayoutItem",
        "size": {"xl": {"gridWidth": largura, "gridHeight": altura}},
        "widget": {
            "type": "insight",
            "insight": {"identifier": {"id": viz_id, "type": "visualizationObject"}},
            "title": titulo,
            "description": "",
            "drills": [],
            "ignoreDashboardFilters": [],
            "properties": {},
            "localIdentifier": f"w{n}",
        },
    }


def _secao(titulo: str, descricao: str, itens: list[dict]) -> dict:
    return {"type": "IDashboardLayoutSection", "header": {"title": titulo, "description": descricao}, "items": itens}


def dashboard() -> dict:
    titulos = {v["id"]: v["title"] for v in VISUALIZACOES}
    n = iter(range(1, 100))

    def it(viz, largura, altura):
        return _item(viz, titulos[viz], largura, altura, next(n))

    return {
        "id": DASHBOARD_ID,
        "title": "Museus do Brasil",
        "description": "Cobertura, gestão e acessibilidade dos museus brasileiros. Cadastro Nacional de Museus (Ibram) "
        "e Censo 2022. Mesmas métricas do painel em Python e do dbt.",
        "content": {
            "version": "2",
            "filterContextRef": {"identifier": {"id": FILTROS_ID, "type": "filterContext"}},
            "layout": {
                "type": "IDashboardLayout",
                "sections": [
                    _secao(
                        "Onde há museu no Brasil",
                        'Números de capa. Museu ativo = status "Aberto" no cadastro.',
                        [
                            it("kpi_museus_ativos", 3, 8),
                            it("kpi_museus_100k", 3, 8),
                            it("kpi_municipios_com_museu", 3, 8),
                            it("kpi_pop_sem_museu", 3, 8),
                        ],
                    ),
                    _secao(
                        "Território",
                        "Densidade por UF, população sem museu e cobertura por porte do município.",
                        [it("uf_museus_100k", 6, 24), it("regiao_pop_sem_museu", 6, 12), it("porte_cobertura", 6, 12)],
                    ),
                    _secao(
                        "Gestão",
                        "Índice de gestão (0-100) e plano museológico, exigido por lei desde 2009.",
                        [it("gestao_por_natureza", 6, 12), it("faixa_gestao", 6, 12)],
                    ),
                    _secao(
                        "Acessibilidade",
                        "Museus ativos que não declararam nenhum recurso de acessibilidade.",
                        [it("tipo_sem_acessibilidade", 12, 14)],
                    ),
                ],
            },
        },
    }


def filtros() -> dict:
    """Filtros do dashboard: região e UF (os mesmos do painel em Python)."""
    return {
        "id": FILTROS_ID,
        "title": "Filtros: Museus do Brasil",
        "content": {
            "version": "2",
            "filters": [
                {
                    "attributeFilter": {
                        "displayForm": {"identifier": {"id": REGIAO, "type": "label"}},
                        "negativeSelection": True,
                        "attributeElements": {"uris": []},
                        "localIdentifier": "f_regiao",
                    }
                },
                {
                    "attributeFilter": {
                        "displayForm": {"identifier": {"id": UF, "type": "label"}},
                        "negativeSelection": True,
                        "attributeElements": {"uris": []},
                        "localIdentifier": "f_uf",
                    }
                },
            ],
        },
    }


# ------------------------------------------------------------- publicação


class Publicador:
    TIPOS: ClassVar[dict[str, tuple[str, str]]] = {
        "visualizationObject": ("visualizationObjects", "createEntityVisualizationObjects"),
        "filterContext": ("filterContexts", "createEntityFilterContexts"),
        "analyticalDashboard": ("analyticalDashboards", "createEntityAnalyticalDashboards"),
    }

    def __init__(self) -> None:
        self.mcp = ClienteMCP()
        self.ws = os.environ["GOODDATA_WORKSPACE"]
        self.base = os.environ["GOODDATA_HOST"].rstrip("/") + f"/api/v1/entities/workspaces/{self.ws}"
        self.http = httpx.Client(
            timeout=120,
            headers={
                "Authorization": f"Bearer {os.environ['GOODDATA_TOKEN']}",
                "Content-Type": "application/vnd.gooddata.api+json",
            },
        )

    def publicar(self, tipo: str, obj: dict) -> str:
        colecao, ferramenta = self.TIPOS[tipo]
        corpo = {
            "type": tipo,
            "id": obj["id"],
            "attributes": {k: obj[k] for k in ("title", "description", "content") if k in obj},
        }
        existe = self.http.get(f"{self.base}/{colecao}/{obj['id']}").status_code == 200
        if existe:
            r = self.http.put(f"{self.base}/{colecao}/{obj['id']}", json={"data": corpo})
            r.raise_for_status()
            return "atualizado (REST)"
        r = self.mcp.chamar("call_tool", {"name": ferramenta, "arguments": {"workspaceId": self.ws, "data": corpo}})
        if r.get("isError"):
            raise RuntimeError(f"{obj['id']}: {r['content'][0]['text'][:500]}")
        return "criado (MCP)"

    def executar(self, viz: dict) -> str:
        """Roda a consulta da visualização pela API de execução (AFM).

        O MCP tem execute_visualization, mas ela não está liberada no plano trial;
        a consulta é montada a partir dos mesmos buckets da visualização."""
        import time

        medidas, atributos = [], []
        for b in viz["content"]["buckets"]:
            for item in b["items"]:
                if "measure" in item:
                    m = item["measure"]
                    medidas.append(
                        {
                            "localIdentifier": m["localIdentifier"],
                            "definition": {"measure": {"item": m["definition"]["measureDefinition"]["item"]}},
                        }
                    )
                else:
                    a = item["attribute"]
                    atributos.append({"localIdentifier": a["localIdentifier"], "label": a["displayForm"]})
        corpo = {
            "execution": {"attributes": atributos, "measures": medidas, "filters": []},
            "resultSpec": {
                "dimensions": [
                    {"localIdentifier": "d0", "itemIdentifiers": [a["localIdentifier"] for a in atributos]},
                    {"localIdentifier": "d1", "itemIdentifiers": ["measureGroup"]},
                ]
            },
        }
        url = os.environ["GOODDATA_HOST"].rstrip("/") + f"/api/v1/actions/workspaces/{self.ws}/execution/afm/execute"
        h = {"Authorization": self.http.headers["Authorization"], "Content-Type": "application/json"}
        r = httpx.post(url, json=corpo, headers=h, timeout=120)
        if r.status_code >= 400:
            return f"ERRO {r.status_code}: {r.text[:300]}"
        link = r.json()["executionResponse"]["links"]["executionResult"]
        for _ in range(30):
            res = httpx.get(f"{url}/result/{link}", headers=h, timeout=120)
            if res.status_code == 200:
                dados = res.json()
                linhas = dados["data"]
                n = len(linhas) if linhas and isinstance(linhas[0], list) else 1
                rotulos = [
                    h["attributeHeader"]["labelValue"]
                    for h in (dados["dimensionHeaders"][0]["headerGroups"][0]["headers"] if atributos else [])
                ][:3]
                return f"{n} linha(s); primeiras: {rotulos} {str(linhas[:3])[:120]}"
            time.sleep(1)
        return "sem resultado"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="gooddata.dashboard")
    p.add_argument("--validar", action="store_true")
    p.add_argument("--pdf", action="store_true", help="só exporta o dashboard em PDF para docs/")
    args = p.parse_args()
    if args.pdf:
        print("PDF salvo em", exportar_pdf())
        return 0
    pub = Publicador()

    if not args.validar:
        for v in VISUALIZACOES:
            print(f"{v['id']:<28} {pub.publicar('visualizationObject', v)}")
        print(f"{FILTROS_ID:<28} {pub.publicar('filterContext', filtros())}")
        print(f"{DASHBOARD_ID:<28} {pub.publicar('analyticalDashboard', dashboard())}")

    print("\nconferência (cada visualização executada pela API de execução):")
    for v in VISUALIZACOES:
        print(f"- {v['id']}: {pub.executar(v)[:240]}")
    host = os.environ["GOODDATA_HOST"].rstrip("/")
    print(f"\n{host}/dashboards/#/workspace/{pub.ws}/dashboard/{DASHBOARD_ID}")
    return 0


def exportar_pdf(destino: str = "docs/gooddata-dashboard.pdf") -> str:
    """Exporta o dashboard em PDF pelo MCP (run_export) e salva no repositório."""
    import base64
    from pathlib import Path

    pub = Publicador()
    r = pub.mcp.chamar(
        "call_tool",
        {"name": "run_export", "arguments": {"mode": "visual", "dashboard_id": DASHBOARD_ID, "format": "PDF"}},
    )
    info = json.loads(r["content"][0]["text"])
    if info.get("inline_base64"):
        conteudo = base64.b64decode(info["inline_base64"])
    else:  # arquivos maiores que 2 MB vêm só como link
        conteudo = pub.http.get(info["download_url"]).content
    caminho = Path(__file__).resolve().parent.parent / destino
    caminho.write_bytes(conteudo)
    return str(caminho)


if __name__ == "__main__":
    raise SystemExit(main())
