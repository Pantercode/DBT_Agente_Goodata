"""Painel Museus do Brasil (FastAPI + Plotly).

    uvicorn painel.app:app --reload          # local, http://127.0.0.1:8000
    Vercel: api/index.py importa `app` daqui.

Server-side: cada página monta as figuras em Python e o navegador só
renderiza o JSON com plotly.js. Filtros (região/UF) são query string, então
toda visão tem URL compartilhável.
"""

from __future__ import annotations

import itertools
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from consumo import dados
from painel import consultas as q
from painel import graficos as g

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
log = logging.getLogger("painel")

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Museus do Brasil", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.filters["br"] = g.fmt_br
templates.env.filters["pct"] = g.fmt_pct
# "capitalize" do Jinja põe o resto em minúsculo ("UF" vira "uf"); aqui só a primeira letra muda.
templates.env.filters["frase"] = lambda t: (t[:1].upper() + t[1:]) if t else t

PAGINAS = [
    ("panorama", "/", "Panorama"),
    ("territorio", "/territorio", "Território"),
    ("gestao", "/gestao", "Gestão"),
    ("acessibilidade", "/acessibilidade", "Acessibilidade"),
    ("qualidade", "/qualidade", "Qualidade"),
    ("agente", "/agente", "Assistente"),
]


def _filtro(request: Request) -> q.Filtro:
    uf = (request.query_params.get("uf") or "").upper() or None
    regiao = (request.query_params.get("regiao") or "").upper() or None
    validas = {u["uf_sigla"] for u in q.ufs()}
    return q.Filtro(regiao=regiao if regiao in q.REGIOES else None, uf=uf if uf in validas else None)


def _grafico(
    id_: str,
    titulo: str,
    fig,
    *,
    nota: str = "",
    colunas: list[str] | None = None,
    linhas: list[list] | None = None,
    largura: str = "metade",
) -> dict:
    return {
        "id": id_,
        "titulo": titulo,
        "nota": nota,
        "fig": g.para_json(fig),
        "largura": largura,
        "tabela": {"colunas": colunas or [], "linhas": linhas or []},
    }


def _render(request: Request, pagina: str, contexto: dict) -> HTMLResponse:
    f = _filtro(request)
    status = dados.status_pipeline()
    return templates.TemplateResponse(
        request,
        f"{pagina}.html",
        {
            "pagina": pagina,
            "paginas": PAGINAS,
            "filtro": f,
            "regioes": q.REGIOES,
            "ufs": q.ufs(),
            "status": status,
            "dt_referencia": q.indicadores(q.Filtro())["dt_referencia"],
            "itens_paleta": _itens_paleta(),
            "quarentena": q.quarentena_pendente(),
            **contexto,
        },
    )


def _itens_paleta() -> list[dict]:
    """Destinos da paleta de comandos (Ctrl+K): páginas, regiões e UFs."""
    itens = [{"tipo": "Página", "rotulo": nome, "href": href} for _, href, nome in PAGINAS]
    itens += [
        {"tipo": "Região", "rotulo": nome, "busca": sigla, "href": f"/?regiao={sigla}"}
        for sigla, nome in q.REGIOES.items()
    ]
    itens += [
        {
            "tipo": "UF",
            "rotulo": u["uf_sigla"],
            "busca": q.REGIOES.get(u["regiao_sigla"], ""),
            "href": f"/?uf={u['uf_sigla']}",
        }
        for u in q.ufs()
    ]
    return itens


@app.get("/", response_class=HTMLResponse)
def panorama(request: Request):
    f = _filtro(request)
    k = q.indicadores(f)
    brasil = q.indicadores(q.Filtro())
    todas = q.todas_ufs()
    recorte = {u["uf_sigla"] for u in q.cobertura_uf(f)}
    graficos = [
        _grafico(
            "ranking",
            "Museus ativos por 100 mil habitantes",
            g.ranking_ufs(todas, brasil["museus_por_100k_hab"], recorte if (f.uf or f.regiao) else None),
            nota="A linha vertical é a média nacional. Em destaque, o recorte do filtro.",
            colunas=["UF", "Por 100 mil", "Museus ativos", "População"],
            linhas=[
                [u["uf_sigla"], g.fmt_br(u["museus_por_100k_hab"], 2), u["qtd_museus_ativos"], g.fmt_br(u["populacao"])]
                for u in todas
            ],
            largura="cinco",
        ),
        _grafico(
            "decadas",
            "Quando os museus de hoje foram abertos",
            g.aberturas(q.aberturas_por_decada(f)),
            nota="Museus atualmente cadastrados, pela década de abertura informada.",
            largura="inteira",
        ),
    ]
    mapa = g.para_json(g.mapa_densidade(todas, dados.malha_uf(), recorte))
    regioes = q.participacao_regioes()
    return _render(
        request,
        "panorama",
        {
            "k": k,
            "mapa": mapa,
            "graficos": graficos,
            "regioes_fig": g.para_json(g.populacao_vs_museus(regioes)),
            "regioes_tabela": regioes,
            "linha_do_tempo": _linha_do_tempo(q.marcos_linha_do_tempo(f)),
            "vizinhos": _vizinhos(f),
        },
    )


# Eixo da linha do tempo: marcas igualmente espaçadas, escala não linear de
# propósito (o século XIX tem poucos museus; os anos 2000 têm um quarto deles).
MARCAS_TEMPO = [1800, 1850, 1900, 1950, 1980, 2000, 2010, 2020, 2030]


def _posicao(ano: float) -> float:
    for i, (a, b) in enumerate(itertools.pairwise(MARCAS_TEMPO)):
        if a <= ano <= b:
            return (i + (ano - a) / (b - a)) / (len(MARCAS_TEMPO) - 1) * 100
    return 0.0 if ano < MARCAS_TEMPO[0] else 100.0


def _linha_do_tempo(m: dict) -> dict:
    eventos = []
    if m["mais_antigo"]:
        a = m["mais_antigo"]
        eventos.append(
            {
                "ano": a["ano_abertura"],
                "linha": 1,
                "ancora": "inicio",
                "ponto": "mudo",
                "texto": f"{a['nome_museu']}",
                "selo": f"{a['ano_abertura']} · mais antigo ativo",
            }
        )
    if m["pico"]:
        eventos.append(
            {
                "ano": m["pico"]["decada"] + 10,
                "linha": 3,
                "ancora": "fim",
                "ponto": "acento",
                "texto": f"Anos {m['pico']['decada']}: {g.fmt_br(m['pico']['qtd'])} aberturas",
                "selo": "Década com mais museus",
            }
        )
    eventos.append(
        {
            "ano": 2009,
            "linha": 2,
            "ancora": "fim",
            "ponto": "azul",
            "texto": "Estatuto de Museus e criação do Ibram",
            "selo": "2009 · Leis 11.904 e 11.906",
        }
    )
    for e in eventos:
        e["posicao"] = round(_posicao(e["ano"]), 2)
    marcas = [{"rotulo": str(a), "posicao": round(_posicao(a), 2)} for a in MARCAS_TEMPO[:-1]]
    return {"eventos": eventos, "marcas": marcas, "ultimos_dez_anos": m["ultimos_dez_anos"]}


def _vizinhos(f: q.Filtro) -> dict:
    """Setas da faixa de recorte: navegam Brasil -> regiões -> Brasil."""
    ordem = [None, *q.REGIOES]
    atual = None if f.uf else f.regiao
    i = ordem.index(atual) if atual in ordem else 0

    def href(r):
        return "/" if r is None else f"/?regiao={r}"

    return {"anterior": href(ordem[i - 1]), "proximo": href(ordem[(i + 1) % len(ordem)])}


@app.get("/territorio", response_class=HTMLResponse)
def territorio(request: Request):
    f = _filtro(request)
    porte = q.cobertura_por_porte(f)
    sem = q.maiores_municipios_sem_museu(f)
    pontos = q.museus_no_mapa(f)
    graficos = [
        _grafico(
            "porte",
            "Cobertura por porte do município",
            g.cobertura_por_porte(porte),
            nota="Proporção de municípios em cada classe de cobertura, por faixa de população (Censo 2022).",
            colunas=["Faixa", "Classe", "Municípios", "População"],
            linhas=[
                [r["faixa_populacional"], r["classe_cobertura"], r["qtd_municipios"], g.fmt_br(r["populacao"])]
                for r in porte
            ],
        ),
        _grafico(
            "sem-museu",
            "Maiores municípios sem nenhum museu ativo",
            g.maiores_sem_museu(sem),
            colunas=["Município", "População"],
            linhas=[[m["municipio_rotulo"], g.fmt_br(m["populacao"])] for m in sem],
        ),
        _grafico(
            "pontos",
            f"{g.fmt_br(len(pontos))} museus ativos com coordenada",
            g.mapa_pontos(pontos, dados.malha_uf()),
            nota="Cada ponto é um museu, pela natureza administrativa.",
            largura="inteira",
        ),
    ]
    return _render(
        request,
        "secao",
        {
            "titulo": "Onde há museu, e onde não há",
            "k": q.indicadores(f),
            "graficos": graficos,
            "lead": "A distância até o museu mais próximo é, para um terço do país, a distância até outra cidade.",
        },
    )


@app.get("/gestao", response_class=HTMLResponse)
def gestao(request: Request):
    f = _filtro(request)
    criterios = q.gestao_criterios(f)
    faixas = q.faixas_gestao(f)
    graficos = [
        _grafico(
            "criterios",
            "Instrumentos de gestão por natureza administrativa",
            g.heatmap_criterios(criterios),
            nota="Percentual de museus ativos que declararam ter cada instrumento. Entre parênteses, o número de museus.",
            colunas=["Natureza", *[r for _, r in g.CRITERIOS]],
            linhas=[[r["natureza_administrativa"], *[g.fmt_pct(r[c], 0) for c, _ in g.CRITERIOS]] for r in criterios],
            largura="inteira",
        ),
        _grafico(
            "faixas",
            "Distribuição do índice de gestão",
            g.faixas_gestao(faixas),
            nota="Faixas: sem instrumentos (0), incipiente (1-39), em estruturação (40-69), estruturada (70+).",
            colunas=["Faixa", "Natureza", "Museus"],
            linhas=[[r["faixa"], r["natureza_administrativa"], r["qtd"]] for r in faixas],
            largura="inteira",
        ),
    ]
    return _render(
        request,
        "secao",
        {
            "titulo": "Como os museus se organizam",
            "k": q.indicadores(f),
            "graficos": graficos,
            "lead": "O plano museológico é exigido por lei desde 2009. Ainda é exceção.",
        },
    )


@app.get("/acessibilidade", response_class=HTMLResponse)
def acessibilidade(request: Request):
    f = _filtro(request)
    rec = q.recursos_acessibilidade(f)
    dims = q.acessibilidade_dimensoes(f)
    graficos = [
        _grafico(
            "dimensoes",
            "Quantas dimensões de acessibilidade cada museu atende",
            g.dimensoes_acessibilidade(dims),
            nota="Física, sensorial (auditiva/visual) e atendimento a estrangeiros.",
            colunas=["Dimensões", "Museus"],
            linhas=[[r["dimensoes"], r["qtd"]] for r in dims],
            largura="inteira",
        ),
        _grafico(
            "fisica",
            "Recursos de acessibilidade física",
            g.recursos(rec, "Física"),
            colunas=["Recurso", "% dos museus", "Museus"],
            linhas=[[r["recurso"], g.fmt_pct(r["pct"]), r["qtd"]] for r in rec if r["dimensao"] == "Física"],
        ),
        _grafico(
            "sensorial",
            "Recursos para deficiência auditiva ou visual",
            g.recursos(rec, "Sensorial"),
            colunas=["Recurso", "% dos museus", "Museus"],
            linhas=[[r["recurso"], g.fmt_pct(r["pct"]), r["qtd"]] for r in rec if r["dimensao"] == "Sensorial"],
        ),
    ]
    return _render(
        request,
        "secao",
        {
            "titulo": "Quem consegue entrar",
            "k": q.indicadores(f),
            "graficos": graficos,
            "lead": "Rampa é o recurso mais comum. Braille, Libras e maquete tátil ainda são raros.",
        },
    )


@app.get("/qualidade", response_class=HTMLResponse)
def qualidade(request: Request):
    f = _filtro(request)
    comp = q.completude(f)
    hist = q.historico_testes()
    testes = q.ultimos_testes()
    graficos = [
        _grafico(
            "completude",
            "Preenchimento dos campos-chave do cadastro",
            g.heatmap_completude(comp),
            nota="Campos menos preenchidos no topo. É aqui que os números do painel ficam mais frágeis.",
            colunas=["UF", "Campo", "Preenchido"],
            linhas=[[r["uf_sigla"], r["campo"], g.fmt_pct(r["pct_preenchido"], 0)] for r in comp],
            largura="inteira",
        ),
        _grafico(
            "historico",
            "Testes de qualidade por execução",
            g.historico_testes(hist),
            colunas=["Execução", "Aprovados", "Avisos", "Reprovados"],
            linhas=[[str(r["executado_em"])[:16], r["aprovados"], r["avisos"], r["reprovados"]] for r in hist],
            largura="inteira",
        ),
    ]
    return _render(request, "qualidade", {"graficos": graficos, "testes": testes, "coleta": q.saude_coleta()})


@app.get("/agente", response_class=HTMLResponse)
def agente_pagina(request: Request):
    return _render(request, "agente", {"agente_ativo": bool(os.environ.get("GEMINI_API_KEY"))})


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=3, max_length=1000)
    historico: list[dict] = Field(default_factory=list, max_length=20)


@app.post("/api/agente")
def api_agente(corpo: Pergunta):
    from agente.nucleo import AgenteIndisponivel, perguntar  # import tardio: o painel sobe sem o SDK configurado

    try:
        return perguntar(corpo.pergunta, corpo.historico).para_dict()
    except AgenteIndisponivel as exc:
        return JSONResponse({"erro": str(exc)}, status_code=503)


@app.get("/api/saude")
def saude():
    return {"ok": True, "tabelas": len(dados.tabelas()), "pipeline": dados.status_pipeline().get("status")}
