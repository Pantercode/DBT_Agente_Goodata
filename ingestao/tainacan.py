"""Cliente da API Tainacan do MuseusBr (cadastro.museus.gov.br).

O MuseusBr saiu da plataforma Mapas Culturais (museus.cultura.gov.br, que é a
URL ainda citada na Base dos Dados) e hoje roda em WordPress + Tainacan. A API
é pública e não pede autenticação.

O payload bruto de um item tem ~45 KB porque cada metadado vem renderizado em
HTML (`value_as_html`), com thumbnails etc. Guardamos só o que tem valor
analítico; ver `simplificar_valor`. A decisão está em docs/decisoes/002.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

from ingestao.http import get_json, novo_cliente

log = logging.getLogger(__name__)

BASE = "https://cadastro.museus.gov.br/wp-json/tainacan/v2"


@dataclass(frozen=True)
class Colecao:
    id: int
    entidade: str  # nome da pasta no lake


COLECOES = {
    "museus": Colecao(208, "museus"),
    "pontos_memoria": Colecao(179824, "pontos_memoria"),
}

ITENS_POR_PAGINA = 48  # 96 derruba o servidor (resposta vazia), 24 fica lento demais
WORKERS = 4  # ser educado: é infraestrutura pública


def listar_metadados(cliente: httpx.Client, colecao_id: int) -> list[dict]:
    corpo, _ = get_json(cliente, f"{BASE}/collection/{colecao_id}/metadata", {"perpage": 500})
    return [
        {
            "id": m["id"],
            "slug": m["slug"],
            "nome": m["name"],
            "tipo": m["metadata_type"].rsplit("\\", 1)[-1].lower(),
            "multiplo": m.get("multiple") == "yes",
        }
        for m in corpo
    ]


def _termo(v: dict) -> dict:
    return {"id": v.get("id"), "nome": v.get("name"), "pai": v.get("parent") or None}


def simplificar_valor(valor: object) -> object:
    """Reduz o valor de um metadado Tainacan à sua forma analítica.

    - taxonomia      -> {"id", "nome", "pai"} (ou lista disso)
    - composto       -> lista de {"metadatum_id", "valor"}
    - texto/número   -> string, como veio (a tipagem é feita no staging)
    - vazio/false    -> None (Tainacan usa `false` para taxonomia não preenchida)
    """
    if valor is False or valor == "" or valor == []:
        return None
    if isinstance(valor, dict):
        if "taxonomy" in valor:
            return _termo(valor)
        return valor
    if isinstance(valor, list):
        saida = []
        for v in valor:
            if isinstance(v, dict) and "taxonomy" in v:
                saida.append(_termo(v))
            elif isinstance(v, dict) and "metadatum_id" in v:
                saida.append({"metadatum_id": v["metadatum_id"], "valor": v.get("value_as_string") or v.get("value")})
            elif isinstance(v, list):  # composto com várias linhas
                saida.append([simplificar_valor(x) for x in v])
            else:
                saida.append(v)
        return saida or None
    return valor


def simplificar_item(item: dict) -> dict:
    return {
        "item_id": item["id"],
        "slug": item.get("slug"),
        "url": item.get("url"),
        "status_publicacao": item.get("status"),
        "titulo": item.get("title"),
        "descricao": item.get("description"),
        "criado_em": item.get("creation_date"),  # dd/mm/aaaa
        "modificado_em": item.get("modification_date"),
        "metadados": {slug: simplificar_valor(m.get("value")) for slug, m in (item.get("metadata") or {}).items()},
    }


def _pagina(colecao_id: int, pagina: int, campos_meta: str) -> list[dict]:
    with novo_cliente() as cliente:
        corpo, _ = get_json(
            cliente,
            f"{BASE}/collection/{colecao_id}/items",
            {
                "perpage": ITENS_POR_PAGINA,
                "paged": pagina,
                "orderby": "id",  # a API valida em minúsculo
                "order": "ASC",
                "fetch_only": "title,description,creation_date,modification_date,meta",
                "fetch_only_meta": campos_meta,
            },
        )
    itens = corpo.get("items", [])
    log.info("coleção %s página %s: %s itens", colecao_id, pagina, len(itens))
    return [simplificar_item(i) for i in itens]


def extrair_colecao(colecao: Colecao) -> tuple[list[dict], list[dict], int, float]:
    """Retorna (itens, metadados, total_informado, duração)."""
    inicio = time.monotonic()
    with novo_cliente() as cliente:
        metadados = listar_metadados(cliente, colecao.id)
        _, headers = get_json(cliente, f"{BASE}/collection/{colecao.id}/items", {"perpage": 1, "fetch_only": "title"})
    total = int(headers.get("x-wp-total", 0))
    paginas = -(-total // ITENS_POR_PAGINA)
    campos_meta = ",".join(str(m["id"]) for m in metadados)
    log.info("coleção %s: %s itens em %s páginas", colecao.id, total, paginas)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        lotes = list(pool.map(lambda p: _pagina(colecao.id, p, campos_meta), range(1, paginas + 1)))

    # Ordenação por ID + dedup: se um item for criado durante a extração a paginação
    # desliza e o mesmo ID pode aparecer em duas páginas.
    vistos: dict[int, dict] = {}
    for lote in lotes:
        for item in lote:
            vistos[item["item_id"]] = item
    itens = sorted(vistos.values(), key=lambda i: i["item_id"])
    return itens, metadados, total, time.monotonic() - inicio
