"""Fontes de referência do IBGE: municípios, população (Censo 2022) e malha de UFs."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ingestao.http import get_json, novo_cliente

URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
# Tabela 4709 do SIDRA: população residente, Censo 2022, nível município (n6).
URL_POPULACAO = "https://apisidra.ibge.gov.br/values/t/4709/n6/all/v/93/p/2022"
URL_MALHA_UF = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo+json&intrarregiao=UF&qualidade=minima"
)
URL_UFS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"


def extrair_municipios() -> tuple[list[dict], float]:
    inicio = time.monotonic()
    with novo_cliente() as c:
        corpo, _ = get_json(c, URL_MUNICIPIOS)
    registros = []
    for m in corpo:
        # Alguns municípios novos vêm com microrregiao = null; a UF fica em regiao-imediata.
        micro = m.get("microrregiao") or {}
        meso = micro.get("mesorregiao") or {}
        imediata = m.get("regiao-imediata") or {}
        intermediaria = imediata.get("regiao-intermediaria") or {}
        uf = meso.get("UF") or intermediaria.get("UF") or {}
        registros.append(
            {
                "municipio_id": m["id"],
                "nome": m["nome"],
                "microrregiao": micro.get("nome"),
                "mesorregiao": meso.get("nome"),
                "regiao_imediata": imediata.get("nome"),
                "regiao_intermediaria": intermediaria.get("nome"),
                "uf_id": uf.get("id"),
                "uf_sigla": uf.get("sigla"),
                "uf_nome": uf.get("nome"),
                "regiao_sigla": (uf.get("regiao") or {}).get("sigla"),
                "regiao_nome": (uf.get("regiao") or {}).get("nome"),
            }
        )
    return registros, time.monotonic() - inicio


def extrair_populacao() -> tuple[list[dict], float]:
    inicio = time.monotonic()
    with novo_cliente() as c:
        corpo, _ = get_json(c, URL_POPULACAO)
    # A primeira linha do SIDRA é o cabeçalho com os rótulos das colunas.
    registros = [
        {"municipio_id": int(r["D1C"]), "municipio_rotulo": r["D1N"], "ano": int(r["D3C"]), "populacao": r["V"]}
        for r in corpo[1:]
    ]
    return registros, time.monotonic() - inicio


def baixar_malha_uf(destino: Path) -> Path:
    """GeoJSON das UFs, com a sigla da UF em `properties.sigla` (para o choropleth)."""
    with novo_cliente() as c:
        malha, _ = get_json(c, URL_MALHA_UF)
        ufs, _ = get_json(c, URL_UFS)
    sigla_por_id = {str(u["id"]): u["sigla"] for u in ufs}
    for f in malha["features"]:
        codigo = str(f["properties"]["codarea"])
        f["properties"]["sigla"] = sigla_por_id.get(codigo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(malha, ensure_ascii=False), encoding="utf-8")
    return destino
