"""Ajuste de orientação de polígonos GeoJSON para o Plotly (d3-geo).

A malha do IBGE vem com o anel externo em sentido anti-horário (RFC 7946).
O d3-geo, usado pelo Plotly em `go.Choropleth`, trabalha em coordenadas
esféricas e interpreta anel anti-horário como "o globo inteiro menos este
polígono": cada UF vira um retângulo que cobre o mapa. A correção é inverter:
externo horário, buracos anti-horários.
"""

from __future__ import annotations

import itertools


def _area_assinada(anel: list[list[float]]) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in itertools.pairwise(anel)) / 2


def _orientar(anel: list, horario: bool) -> list:
    eh_horario = _area_assinada(anel) < 0
    return anel if eh_horario == horario else anel[::-1]


def _poligono(aneis: list) -> list:
    return [_orientar(a, horario=(i == 0)) for i, a in enumerate(aneis)]


def orientar_para_d3(geojson: dict) -> dict:
    for feature in geojson["features"]:
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            geom["coordinates"] = _poligono(geom["coordinates"])
        elif geom["type"] == "MultiPolygon":
            geom["coordinates"] = [_poligono(p) for p in geom["coordinates"]]
    return geojson
