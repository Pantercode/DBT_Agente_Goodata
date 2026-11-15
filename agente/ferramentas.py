"""Ferramentas que o agente pode chamar.

Cada ferramenta é uma função Python comum + uma declaração JSON Schema. O
modelo nunca executa nada diretamente: ele pede, o `nucleo` valida e roda.

Regras de desenho:
- Saídas pequenas e estruturadas. O modelo raciocina melhor com 30 linhas
  bem nomeadas do que com 3 mil; `consultar_sql` corta em 50 linhas e avisa.
- Erro vira resultado, não exceção. O modelo recebe a mensagem e corrige
  (ex.: nome de coluna errado), em vez de a conversa quebrar.
- Nenhuma ferramenta escreve. O gerador de modelos dbt devolve texto; quem
  grava no repositório é uma pessoa, via PR.
"""

from __future__ import annotations

import decimal
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from agente.guarda_sql import SQLRecusado, validar
from consumo import dados

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLOS = RAIZ / "ai_templates"
LINHAS_NO_CONTEXTO = 50


def _serializavel(valor: Any) -> Any:
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _serializavel(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_serializavel(v) for v in valor]
    return valor


# ------------------------------------------------------------------ funções


def listar_tabelas() -> dict:
    modelos = dados.catalogo()["modelos"]
    return {
        "tabelas": [
            {"nome": nome, "descricao": m["descricao"][:300], "qtd_colunas": len(m["colunas"])}
            for nome, m in sorted(modelos.items())
        ],
        "observacao": "Todas ficam no schema `publicado`. Use descrever_tabela antes de escrever SQL.",
    }


def descrever_tabela(tabela: str) -> dict:
    modelos = dados.catalogo()["modelos"]
    nome = tabela.removeprefix("publicado.")
    if nome not in modelos:
        return {"erro": f"Tabela `{tabela}` não existe. Opções: {', '.join(sorted(modelos))}"}
    m = modelos[nome]
    amostra = dados.consultar(f"select * from publicado.{nome} limit 3")
    return {
        "tabela": m["tabela"],
        "descricao": m["descricao"],
        "colunas": m["colunas"],
        "depende_de": m["depende_de"],
        "testes_de_qualidade": m["testes"],
        "amostra": _serializavel(amostra),
    }


def consultar_sql(sql: str, objetivo: str) -> dict:
    try:
        validado = validar(sql, set(dados.tabelas()))
    except SQLRecusado as exc:
        return {"erro": str(exc), "dica": "Corrija o SQL e tente de novo."}
    try:
        linhas = dados.consultar(validado.sql)
    except Exception as exc:  # erro do DuckDB (coluna inexistente, tipo...) volta para o modelo
        return {"erro": f"Erro ao executar: {str(exc).splitlines()[0][:400]}", "sql_executado": validado.sql}
    return {
        "objetivo": objetivo,
        "sql_executado": validado.sql,
        "tabelas": list(validado.tabelas),
        "total_linhas": len(linhas),
        "linhas": _serializavel(linhas[:LINHAS_NO_CONTEXTO]),
        "truncado": len(linhas) > LINHAS_NO_CONTEXTO,
    }


def definicao_metrica(termo: str) -> dict:
    cat = dados.catalogo()
    termo_n = termo.lower().replace(" ", "_")
    achados = {k: v for k, v in cat.get("definicoes", {}).items() if termo_n in k or k in termo_n}
    metricas = {
        k: v for k, v in cat.get("metricas", {}).items() if termo_n in k or termo.lower() in v["rotulo"].lower()
    }
    if not achados and not metricas:
        return {
            "erro": f"Sem definição para `{termo}`.",
            "definicoes_disponiveis": sorted(cat.get("definicoes", {})),
            "metricas_disponiveis": sorted(cat.get("metricas", {})),
        }
    return {"definicoes": achados, "metricas_semantic_layer": metricas}


def status_qualidade() -> dict:
    status = dados.status_pipeline()
    falhas = dados.consultar("""
        select nome, modelo_alvo, status, falhas, bloqueante
        from publicado.qualidade_testes
        where invocation_id = (select invocation_id from publicado.qualidade_testes order by executado_em desc limit 1)
          and status not in ('pass', 'success')
    """)
    completude = dados.consultar("""
        select campo, round(sum(qtd_preenchidos) * 1.0 / sum(qtd_museus), 3) as pct_preenchido_brasil
        from publicado.mart_completude_cadastro
        group by campo order by 2
    """)
    coleta = dados.consultar("""
        select fonte, dt, status, motivo_quarentena, is_particao_em_uso
        from publicado.mart_saude_coleta order by dt desc limit 10
    """)
    return _serializavel(
        {
            "saude_da_coleta": coleta,
            "ultima_execucao": {k: status.get(k) for k in ("iniciado_em", "finalizado_em", "status", "publicou")},
            "testes_nao_aprovados_na_ultima_execucao": falhas,
            "completude_dos_campos": completude,
        }
    )


def obter_exemplo_canonico(camada: str) -> dict:
    arquivos = {"staging": "staging.sql", "intermediate": "intermediate.sql", "mart": "mart.sql", "yaml": "schema.yml"}
    if camada not in arquivos:
        return {"erro": f"camada deve ser uma de {sorted(arquivos)}"}
    return {
        "camada": camada,
        "convencoes": (EXEMPLOS / "CONVENCOES.md").read_text(encoding="utf-8"),
        "exemplo": (EXEMPLOS / arquivos[camada]).read_text(encoding="utf-8"),
    }


_contador_graficos = 0
TIPOS_GRAFICO = ("barras", "barras_horizontais", "linha", "dispersao")


def criar_grafico(sql: str, tipo: str, x: str, y: str, titulo: str, serie: str | None = None) -> dict:
    """Roda o SQL (mesma validação de consultar_sql) e monta uma figura no tema do painel.

    A figura vai direto para o usuário (chave `_figura`, retirada pelo núcleo
    antes de devolver ao modelo). O modelo recebe só a confirmação e um resumo
    dos dados, para comentar o gráfico sem gastar contexto com o JSON."""
    import json

    import plotly.graph_objects as go

    from painel import tema

    global _contador_graficos
    if tipo not in TIPOS_GRAFICO:
        return {"erro": f"tipo deve ser um de {', '.join(TIPOS_GRAFICO)}"}
    consulta = consultar_sql(sql, f"gráfico: {titulo}")
    if "erro" in consulta:
        return consulta
    try:
        linhas = dados.consultar(consulta["sql_executado"])
    except Exception as exc:
        return {"erro": str(exc).splitlines()[0][:300]}
    if not linhas:
        return {"erro": "A consulta não devolveu linhas; nada para desenhar."}
    faltando = [c for c in (x, y, serie) if c and c not in linhas[0]]
    if faltando:
        return {"erro": f"Colunas {faltando} não estão no resultado. Colunas: {list(linhas[0])}"}
    if len(linhas) > 60 and tipo != "dispersao":
        linhas = linhas[:60]

    def valores(col):
        return [_serializavel(r[col]) for r in linhas]

    grupos = {None: linhas} if not serie else {}
    if serie:
        for r in linhas:
            grupos.setdefault(r[serie], []).append(r)
    cores = [tema.ACENTO, *tema.CATEGORICA.values()]
    if serie and len(grupos) > len(cores):
        return {
            "erro": f"`{serie}` tem {len(grupos)} categorias; o máximo legível é {len(cores)}. Agrupe o resto em 'Outros'."
        }

    fig = go.Figure()
    for i, (nome, rs) in enumerate(grupos.items()):
        xs, ys = [_serializavel(r[x]) for r in rs], [_serializavel(r[y]) for r in rs]
        cor = cores[i]
        if tipo in ("barras", "barras_horizontais"):
            h = tipo == "barras_horizontais"
            fig.add_trace(
                go.Bar(
                    x=ys if h else xs,
                    y=xs if h else ys,
                    orientation="h" if h else "v",
                    name=str(nome) if nome is not None else y,
                    marker=dict(color=cor, cornerradius=4),
                )
            )
        elif tipo == "linha":
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines+markers",
                    name=str(nome or y),
                    line=dict(color=cor, width=2),
                    marker=dict(size=7),
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    name=str(nome or y),
                    marker=dict(color=cor, size=9, line=dict(color=tema.SUPERFICIE, width=2)),
                )
            )
    if tipo == "barras_horizontais":
        fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(
        height=300,
        showlegend=bool(serie),
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis_title=None if tipo != "dispersao" else x,
        yaxis_title=None if tipo != "dispersao" else y,
    )

    _contador_graficos += 1
    return {
        "grafico_id": _contador_graficos,
        "mensagem": "Gráfico exibido ao usuário. Comente em 1-2 frases o que ele mostra; não repita todos os números.",
        "linhas_desenhadas": len(linhas),
        "amostra": _serializavel(linhas[:5]),
        "_figura": json.loads(fig.to_json()),
    }


# ------------------------------------------------------------- declarações

DECLARACOES: list[dict] = [
    {
        "name": "criar_grafico",
        "description": (
            "Mostra um gráfico ao usuário a partir de um SELECT em `publicado`. Use quando a resposta for uma "
            "comparação entre mais de 4 itens, uma evolução no tempo ou quando o usuário pedir um gráfico. "
            "barras_horizontais para ranking de UFs/municípios; linha para série temporal; dispersao para relação "
            "entre duas medidas. Máximo 4 categorias em `serie`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SELECT que devolve as colunas x, y (e serie, se houver)."},
                "tipo": {"type": "string", "enum": list(TIPOS_GRAFICO)},
                "x": {"type": "string", "description": "Coluna do eixo x (categoria ou data)."},
                "y": {"type": "string", "description": "Coluna numérica."},
                "titulo": {"type": "string", "description": "Título curto, em português."},
                "serie": {"type": "string", "description": "Opcional: coluna que separa séries (até 4 valores)."},
            },
            "required": ["sql", "tipo", "x", "y", "titulo"],
        },
    },
    {
        "name": "listar_tabelas",
        "description": "Lista as tabelas publicadas (schema `publicado`) com uma descrição curta de cada uma.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "descrever_tabela",
        "description": "Colunas, tipos, descrições, linhagem, testes de qualidade e 3 linhas de amostra de uma tabela.",
        "parameters": {
            "type": "object",
            "properties": {"tabela": {"type": "string", "description": "Nome da tabela, ex.: agg_cobertura_uf"}},
            "required": ["tabela"],
        },
    },
    {
        "name": "consultar_sql",
        "description": (
            "Executa UMA consulta SELECT (dialeto DuckDB) nas tabelas de `publicado`. Somente leitura; "
            "LIMIT é aplicado automaticamente (máx. 1000). Campos STRUCT acessam-se com ponto "
            "(gestao.indice) e listas com unnest()/list_contains()."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A consulta SELECT."},
                "objetivo": {"type": "string", "description": "Em uma frase, o que esta consulta responde."},
            },
            "required": ["sql", "objetivo"],
        },
    },
    {
        "name": "definicao_metrica",
        "description": "Definição oficial de um termo ou métrica (ex.: museu_ativo, indice_gestao, museus_por_100k).",
        "parameters": {
            "type": "object",
            "properties": {"termo": {"type": "string"}},
            "required": ["termo"],
        },
    },
    {
        "name": "status_qualidade",
        "description": "Estado da última execução do pipeline, testes que não passaram e completude dos campos do cadastro.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "obter_exemplo_canonico",
        "description": (
            "Devolve as convenções do projeto e o exemplo canônico de uma camada dbt (staging, intermediate, "
            "mart ou yaml). Use antes de propor um modelo dbt novo."
        ),
        "parameters": {
            "type": "object",
            "properties": {"camada": {"type": "string", "enum": ["staging", "intermediate", "mart", "yaml"]}},
            "required": ["camada"],
        },
    },
]

FUNCOES = {
    "listar_tabelas": listar_tabelas,
    "descrever_tabela": descrever_tabela,
    "consultar_sql": consultar_sql,
    "definicao_metrica": definicao_metrica,
    "status_qualidade": status_qualidade,
    "obter_exemplo_canonico": obter_exemplo_canonico,
    "criar_grafico": criar_grafico,
}


def executar(nome: str, argumentos: dict) -> dict:
    if nome not in FUNCOES:
        return {"erro": f"Ferramenta `{nome}` não existe."}
    try:
        return FUNCOES[nome](**argumentos)
    except TypeError as exc:
        return {"erro": f"Argumentos inválidos para {nome}: {exc}"}


def resumo_para_log(resultado: dict) -> str:
    texto = json.dumps(resultado, ensure_ascii=False, default=str)
    return texto[:300] + ("…" if len(texto) > 300 else "")
