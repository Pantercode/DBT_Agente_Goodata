"""Figuras Plotly do painel. Cada função recebe linhas já agregadas e devolve
uma figura; nenhuma faz consulta nem cálculo de KPI.

Regras aplicadas (skill de dataviz):
- uma série -> uma cor (acento); identidade categórica só para natureza;
- barras finas, cantos arredondados, sem número em toda barra (só nos extremos);
- um eixo y por gráfico, sempre;
- tooltip em toda marca, e cada gráfico tem uma tabela equivalente no HTML.
"""

from __future__ import annotations

import plotly.graph_objects as go

from painel import tema

CONFIG_PLOTLY = {"displayModeBar": False, "responsive": True, "locale": "pt-BR"}


def _br(n: float | int | None, casas: int = 0) -> str:
    if n is None:
        return "–"
    txt = f"{n:,.{casas}f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x: float | None, casas: int = 1) -> str:
    return "–" if x is None else _br(x * 100, casas) + "%"


def para_json(fig: go.Figure) -> str:
    return fig.to_json()


# ------------------------------------------------------------------ mapa


def mapa_densidade(ufs: list[dict], geojson: dict, selecionadas: set[str] | None = None) -> go.Figure:
    """Coroplético de museus ativos por 100 mil hab. Fora do filtro fica apagado (não some)."""
    selecionadas = selecionadas or {u["uf_sigla"] for u in ufs}
    dentro = [u for u in ufs if u["uf_sigla"] in selecionadas]
    fora = [u for u in ufs if u["uf_sigla"] not in selecionadas]

    fig = go.Figure()
    if fora:
        fig.add_trace(
            go.Choropleth(
                geojson=geojson,
                featureidkey="properties.sigla",
                locations=[u["uf_sigla"] for u in fora],
                z=[0] * len(fora),
                colorscale=[[0, tema.SUPERFICIE_ALTA], [1, tema.SUPERFICIE_ALTA]],
                showscale=False,
                marker_line_color=tema.FUNDO,
                marker_line_width=1.2,
                hoverinfo="skip",
            )
        )
    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.sigla",
            locations=[u["uf_sigla"] for u in dentro],
            z=[u["museus_por_100k_hab"] for u in dentro],
            zmin=0,
            zmax=max(u["museus_por_100k_hab"] for u in ufs),
            colorscale=tema.RAMPA,
            marker_line_color=tema.FUNDO,
            marker_line_width=1.2,
            customdata=[
                [
                    u["qtd_museus_ativos"],
                    _br(u["populacao"]),
                    _pct(u["pct_municipios_com_museu"]),
                    u["ranking_museus_per_capita"],
                ]
                for u in dentro
            ],
            hovertemplate=(
                "<b>%{location}</b><br>%{z:.2f} museus por 100 mil hab.<br>"
                "%{customdata[0]} museus ativos · %{customdata[1]} hab.<br>"
                "%{customdata[2]} dos municípios com museu<br>%{customdata[3]}º no ranking per capita<extra></extra>"
            ),
            colorbar=dict(
                title=dict(text="museus por 100 mil hab.", font=dict(size=11, color=tema.TINTA_MUDA), side="top"),
                orientation="h",
                thickness=8,
                len=0.42,
                x=0.5,
                xanchor="center",
                y=-0.02,
                yanchor="top",
                tickfont=dict(color=tema.TINTA_MUDA, size=11),
                outlinewidth=0,
            ),
        )
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=56), height=600)
    return fig


def mapa_pontos(museus: list[dict], geojson: dict) -> go.Figure:
    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.sigla",
            locations=[f["properties"]["sigla"] for f in geojson["features"]],
            z=[0] * len(geojson["features"]),
            colorscale=[[0, tema.SUPERFICIE_ALTA], [1, tema.SUPERFICIE_ALTA]],
            showscale=False,
            marker_line_color=tema.FUNDO,
            marker_line_width=1,
            hoverinfo="skip",
        )
    )
    for natureza, cor in tema.CATEGORICA.items():
        pts = [m for m in museus if m["natureza_administrativa"] == natureza]
        fig.add_trace(
            go.Scattergeo(
                lat=[m["lat"] for m in pts],
                lon=[m["lon"] for m in pts],
                mode="markers",
                name=natureza,
                marker=dict(size=4, color=cor, opacity=0.75, line=dict(width=0)),
                text=[f"{m['nome_museu']}<br>{m['municipio_nome']} - {m['uf_sigla']}" for m in pts],
                hovertemplate="%{text}<extra>" + natureza + "</extra>",
            )
        )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520, legend=dict(y=0.02, x=0.02, orientation="v"))
    return fig


# --------------------------------------------------------------- barras


def ranking_ufs(ufs: list[dict], referencia: float, destaque: set[str] | None = None) -> go.Figure:
    ordenadas = sorted(ufs, key=lambda u: u["museus_por_100k_hab"])
    destaque = destaque or set()
    cores = [tema.ACENTO if (not destaque or u["uf_sigla"] in destaque) else tema.BARRA_NEUTRA for u in ordenadas]
    fig = go.Figure(
        go.Bar(
            x=[u["museus_por_100k_hab"] for u in ordenadas],
            y=[u["uf_sigla"] for u in ordenadas],
            orientation="h",
            marker=dict(color=cores, cornerradius=4),
            customdata=[[u["qtd_museus_ativos"], _br(u["populacao"])] for u in ordenadas],
            hovertemplate="<b>%{y}</b> %{x:.2f} por 100 mil<br>%{customdata[0]} museus · %{customdata[1]} hab.<extra></extra>",
        )
    )
    fig.add_vline(x=referencia, line=dict(color=tema.TINTA_MUDA, width=1))
    fig.add_annotation(
        x=referencia,
        y=1.0,
        yref="paper",
        yanchor="bottom",
        showarrow=False,
        text=f"Brasil {_br(referencia, 2)}",
        font=dict(size=11, color=tema.TINTA_2),
    )
    fig.update_layout(
        height=max(320, 22 * len(ordenadas)),
        xaxis=dict(showgrid=True, title=None),
        yaxis=dict(showgrid=False, tickfont=dict(color=tema.TINTA_2)),
        margin=dict(l=8, r=16, t=24, b=8),
    )
    return fig


def maiores_sem_museu(municipios: list[dict]) -> go.Figure:
    ordenados = list(reversed(municipios))
    fig = go.Figure(
        go.Bar(
            x=[m["populacao"] for m in ordenados],
            y=[m["municipio_rotulo"] for m in ordenados],
            orientation="h",
            marker=dict(color=tema.ACENTO, cornerradius=4),
            hovertemplate="<b>%{y}</b><br>%{x:,.0f} habitantes, nenhum museu ativo<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(280, 26 * len(ordenados)),
        xaxis=dict(title=None, tickformat=",.0f"),
        yaxis=dict(showgrid=False, tickfont=dict(color=tema.TINTA_2)),
    )
    return fig


ORDEM_COBERTURA = ["Sem museu ativo", "1 museu", "2 a 5 museus", "Mais de 5 museus"]
# Classes ordenadas: rampa ordinal (um matiz), não paleta categórica.
CORES_COBERTURA = {
    "Sem museu ativo": tema.ORDINAL[0],
    "1 museu": tema.ORDINAL[1],
    "2 a 5 museus": tema.ORDINAL[2],
    "Mais de 5 museus": tema.ORDINAL[3],
}


def cobertura_por_porte(linhas: list[dict]) -> go.Figure:
    faixas = sorted({r["faixa_populacional"] for r in linhas if r["faixa_populacional"]})
    total = {f: sum(r["qtd_municipios"] for r in linhas if r["faixa_populacional"] == f) for f in faixas}
    fig = go.Figure()
    for classe in ORDEM_COBERTURA:
        valores = []
        for f in faixas:
            n = sum(
                r["qtd_municipios"] for r in linhas if r["faixa_populacional"] == f and r["classe_cobertura"] == classe
            )
            valores.append(n / total[f] if total[f] else 0)
        fig.add_trace(
            go.Bar(
                name=classe,
                x=[f.split(". ", 1)[1] for f in faixas],
                y=valores,
                marker=dict(color=CORES_COBERTURA[classe], line=dict(color=tema.SUPERFICIE, width=2)),
                hovertemplate="%{x}<br>" + classe + ": %{y:.1%}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        height=340,
        yaxis=dict(tickformat=".0%", title=None),
        xaxis=dict(title="porte do município (habitantes)"),
        legend=dict(y=1.14),
    )
    return fig


def aberturas(linhas: list[dict]) -> go.Figure:
    decadas = sorted({r["decada_abertura"] for r in linhas})
    fig = go.Figure()
    for natureza, cor in tema.CATEGORICA.items():
        por_decada = {r["decada_abertura"]: r["qtd_museus"] for r in linhas if r["natureza_administrativa"] == natureza}
        fig.add_trace(
            go.Bar(
                name=natureza,
                x=[f"{d}s" for d in decadas],
                y=[por_decada.get(d, 0) for d in decadas],
                marker=dict(color=cor, line=dict(color=tema.SUPERFICIE, width=2)),
                hovertemplate="%{x}: %{y} museus " + natureza.lower() + "s<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        height=320,
        xaxis=dict(title=None, tickangle=0, nticks=12),
        yaxis=dict(title=None),
        legend=dict(y=1.14),
    )
    return fig


CRITERIOS = [
    ("plano_museologico", "Plano museológico"),
    ("regimento_interno", "Regimento interno"),
    ("documentacao_acervo", "Documentação do acervo"),
    ("politica_aquisicao", "Política de aquisição"),
    ("politica_descarte", "Política de descarte"),
    ("equipe_propria", "Equipe própria"),
]


def heatmap_criterios(linhas: list[dict]) -> go.Figure:
    naturezas = [r["natureza_administrativa"] for r in linhas]
    z = [[r[c] for r in linhas] for c, _ in CRITERIOS]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"{n} ({r['qtd']})" for n, r in zip(naturezas, linhas, strict=True)],
            y=[r for _, r in CRITERIOS],
            zmin=0,
            zmax=1,
            colorscale=tema.RAMPA,
            xgap=3,
            ygap=3,
            text=[[_pct(v, 0) for v in linha] for linha in z],
            texttemplate="%{text}",
            textfont=dict(color=tema.TINTA, size=13),
            hovertemplate="%{y}<br>%{x}: %{z:.1%} dos museus ativos<extra></extra>",
            colorbar=dict(tickformat=".0%", thickness=8, outlinewidth=0, tickfont=dict(color=tema.TINTA_MUDA)),
        )
    )
    fig.update_layout(
        height=360, yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(showgrid=False, side="top")
    )
    return fig


ORDEM_FAIXAS = ["Sem instrumentos", "Incipiente", "Em estruturação", "Estruturada"]


def faixas_gestao(linhas: list[dict]) -> go.Figure:
    fig = go.Figure()
    for natureza, cor in tema.CATEGORICA.items():
        total = sum(r["qtd"] for r in linhas if r["natureza_administrativa"] == natureza) or 1
        por_faixa = {r["faixa"]: r["qtd"] for r in linhas if r["natureza_administrativa"] == natureza}
        fig.add_trace(
            go.Bar(
                name=natureza,
                x=ORDEM_FAIXAS,
                y=[por_faixa.get(f, 0) / total for f in ORDEM_FAIXAS],
                marker=dict(color=cor, cornerradius=4),
                hovertemplate="%{x}<br>" + natureza + ": %{y:.1%}<extra></extra>",
            )
        )
    fig.update_layout(barmode="group", height=320, yaxis=dict(tickformat=".0%", title=None), legend=dict(y=1.14))
    return fig


def recursos(linhas: list[dict], dimensao: str, limite: int = 8) -> go.Figure:
    sel = [r for r in linhas if r["dimensao"] == dimensao][:limite][::-1]
    fig = go.Figure(
        go.Bar(
            x=[r["pct"] for r in sel],
            y=[r["recurso"] for r in sel],
            orientation="h",
            marker=dict(color=tema.ACENTO, cornerradius=4),
            customdata=[r["qtd"] for r in sel],
            hovertemplate="<b>%{y}</b><br>%{x:.1%} dos museus ativos (%{customdata})<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(260, 34 * len(sel)),
        xaxis=dict(tickformat=".0%", title=None),
        yaxis=dict(showgrid=False, tickfont=dict(color=tema.TINTA_2), automargin=True),
    )
    return fig


def dimensoes_acessibilidade(linhas: list[dict]) -> go.Figure:
    rotulos = {0: "Nenhuma", 1: "Uma", 2: "Duas", 3: "Três"}
    total = sum(r["qtd"] for r in linhas) or 1
    cores = [*tema.ORDINAL]
    fig = go.Figure()
    for r in linhas:
        fig.add_trace(
            go.Bar(
                name=rotulos[r["dimensoes"]],
                x=[r["qtd"] / total],
                y=[""],
                orientation="h",
                marker=dict(color=cores[r["dimensoes"]], line=dict(color=tema.SUPERFICIE, width=2)),
                hovertemplate=rotulos[r["dimensoes"]] + " dimensão(ões): %{x:.1%}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        height=130,
        xaxis=dict(tickformat=".0%", showgrid=False, title=None),
        yaxis=dict(visible=False),
        legend=dict(y=1.5),
        margin=dict(l=8, r=8, t=36, b=8),
    )
    return fig


def heatmap_completude(linhas: list[dict]) -> go.Figure:
    campos = sorted(
        {r["campo"] for r in linhas}, key=lambda c: sum(r["pct_preenchido"] for r in linhas if r["campo"] == c)
    )
    ufs = sorted({r["uf_sigla"] for r in linhas})
    idx = {(r["campo"], r["uf_sigla"]): r["pct_preenchido"] for r in linhas}
    z = [[idx.get((c, u)) for u in ufs] for c in campos]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=ufs,
            y=campos,
            zmin=0,
            zmax=1,
            colorscale=tema.RAMPA,
            xgap=2,
            ygap=2,
            hovertemplate="%{y} em %{x}: %{z:.0%} preenchido<extra></extra>",
            colorbar=dict(tickformat=".0%", thickness=8, outlinewidth=0, tickfont=dict(color=tema.TINTA_MUDA)),
        )
    )
    fig.update_layout(height=400, xaxis=dict(showgrid=False, side="top"), yaxis=dict(showgrid=False))
    return fig


def historico_testes(linhas: list[dict]) -> go.Figure:
    x = [str(r["executado_em"])[:16] for r in linhas]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Aprovados",
            x=x,
            y=[r["aprovados"] for r in linhas],
            marker=dict(color=tema.STATUS["bom"], line=dict(color=tema.SUPERFICIE, width=2)),
        )
    )
    fig.add_trace(
        go.Bar(
            name="Avisos",
            x=x,
            y=[r["avisos"] for r in linhas],
            marker=dict(color=tema.STATUS["atencao"], line=dict(color=tema.SUPERFICIE, width=2)),
        )
    )
    fig.add_trace(
        go.Bar(
            name="Reprovados",
            x=x,
            y=[r["reprovados"] for r in linhas],
            marker=dict(color=tema.STATUS["critico"], line=dict(color=tema.SUPERFICIE, width=2)),
        )
    )
    # Com poucas execuções as barras ficariam largas demais; o gap acompanha a quantidade.
    fig.update_layout(
        barmode="stack",
        height=240,
        xaxis=dict(type="category", title=None),
        yaxis=dict(title=None),
        legend=dict(y=1.2),
        bargap=0.75 if len(linhas) < 8 else 0.3,
    )
    return fig


fmt_br = _br
fmt_pct = _pct


# ------------------------------------------------------- cartões da capa


def populacao_vs_museus(regioes: list[dict]) -> go.Figure:
    """Por região: barra larga translúcida = % da população do país; barra âmbar
    dentro = % dos museus ativos. Mesma unidade (% do total nacional), um eixo.
    O rótulo em pílula marca a região com maior sobra de museus em relação à população."""
    ordem = ["N", "NE", "CO", "SE", "S"]
    regioes = sorted(regioes, key=lambda r: ordem.index(r["regiao_sigla"]))
    x = [r["regiao_sigla"] for r in regioes]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x,
            y=[r["pct_populacao"] for r in regioes],
            name="População",
            width=0.62,
            marker=dict(
                color="rgba(255,255,255,0.08)", line=dict(color="rgba(255,255,255,0.10)", width=1), cornerradius=10
            ),
            hovertemplate="%{x}: %{y:.1%} da população<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=x,
            y=[r["pct_museus"] for r in regioes],
            name="Museus ativos",
            width=0.42,
            marker=dict(color=tema.ACENTO, cornerradius=8),
            hovertemplate="%{x}: %{y:.1%} dos museus ativos<extra></extra>",
        )
    )
    destaque = max(regioes, key=lambda r: r["pct_museus"] - r["pct_populacao"])
    topo = max(destaque["pct_museus"], destaque["pct_populacao"])
    fig.add_hline(y=topo, line=dict(color="rgba(244,241,236,0.55)", width=1, dash="dot"))
    fig.add_annotation(
        x=destaque["regiao_sigla"],
        y=topo,
        yanchor="bottom",
        yshift=6,
        showarrow=False,
        xanchor="right" if destaque["regiao_sigla"] == ordem[-1] else "center",
        text=f"<b>{destaque['regiao_nome']}</b> · {_pct(destaque['pct_museus'], 0)} dos museus, "
        f"{_pct(destaque['pct_populacao'], 0)} da população",
        bgcolor=tema.TINTA,
        bordercolor=tema.TINTA,
        borderpad=5,
        font=dict(color=tema.FUNDO, size=11),
    )
    fig.update_layout(
        barmode="overlay",
        height=122,
        showlegend=False,
        margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(color=tema.TINTA_2, size=11)),
        yaxis=dict(visible=False, range=[0, topo * 1.45]),
    )
    return fig
