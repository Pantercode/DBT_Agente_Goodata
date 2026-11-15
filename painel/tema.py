"""Tokens visuais do painel e o template Plotly que os aplica.

Linguagem visual: preto quente, superfícies de vidro escuro e um único acento
âmbar que aparece como luz (brilho nos cartões, barras em destaque).

Paleta categórica (natureza administrativa): âmbar / azul / rosa, validada
contra a superfície #171513 com scripts/validate_palette.js do skill de
dataviz, em modo `--pairs all` (serve para mapa de pontos): todos os checks
passam. O âmbar categórico (#C4821A) é um degrau abaixo do âmbar de destaque
(#E9A23B) porque o claro sai da faixa de luminosidade das séries.

Rampa sequencial (mapa, heatmaps): âmbar, um matiz só, do quase-fundo ao dourado.
"""

import plotly.graph_objects as go
import plotly.io as pio

FUNDO = "#0B0A09"
SUPERFICIE = "#171513"
SUPERFICIE_ALTA = "#211E1B"
LINHA = "#2B2724"
GRADE = "#221F1C"
TINTA = "#F4F1EC"
TINTA_2 = "#A39E96"
TINTA_MUDA = "#6E6A64"
ACENTO = "#E9A23B"
BARRA_NEUTRA = "#3A3632"

CATEGORICA = {"Pública": "#C4821A", "Privada": "#4F8BEA", "Mista": "#C85A8F"}
STATUS = {"bom": "#3FB27F", "atencao": "#E9A23B", "critico": "#E0574F"}

RAMPA = [
    [0.0, "#221A10"],
    [0.2, "#4A3014"],
    [0.4, "#7A4C15"],
    [0.6, "#B06E18"],
    [0.8, "#E09A2E"],
    [1.0, "#FFD48A"],
]
# Classes ordenadas (ordinal): mesma rampa, quatro degraus.
ORDINAL = ["#2E2A26", "#7A4C15", "#C4821A", "#FFC46B"]

FONTE = "Geist, Inter, system-ui, -apple-system, Segoe UI, sans-serif"

pio.templates["museus"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONTE, color=TINTA_2, size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[ACENTO, *CATEGORICA.values()],
        margin=dict(l=8, r=8, t=8, b=8),
        hoverlabel=dict(bgcolor=TINTA, bordercolor=TINTA, font=dict(family=FONTE, color=FUNDO, size=13)),
        # automargin: sem isso o Plotly corta rótulo de eixo maior que a margem fixa
        xaxis=dict(
            gridcolor=GRADE,
            linecolor=LINHA,
            zerolinecolor=LINHA,
            tickfont=dict(color=TINTA_MUDA),
            title=dict(font=dict(color=TINTA_MUDA, size=12)),
            automargin=True,
        ),
        yaxis=dict(
            gridcolor=GRADE,
            linecolor=LINHA,
            zerolinecolor=LINHA,
            tickfont=dict(color=TINTA_MUDA),
            title=dict(font=dict(color=TINTA_MUDA, size=12)),
            automargin=True,
        ),
        legend=dict(font=dict(color=TINTA_2), bgcolor="rgba(0,0,0,0)", orientation="h", y=1.08, x=0),
        bargap=0.28,
        separators=",.",
    )
)
pio.templates.default = "museus"
