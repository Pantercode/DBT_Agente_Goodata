"""O que o agente sabe antes de chamar qualquer ferramenta.

1. Catálogo compacto: tabelas de `publicado` com as colunas e a descrição em
   uma linha. Vai no prompt; o agente não precisa gastar duas chamadas
   (listar + descrever) para descobrir nome de coluna nas perguntas comuns.
2. Exemplos verificados (exemplos_verificados.yaml): os 3 mais parecidos com a
   pergunta entram no prompt como referência. É few-shot com recuperação; o
   agente vê como perguntas desse domínio são respondidas certo neste schema.
3. Feedback: 👍/👎 do chat vão para data/agente/feedback.jsonl. Os aprovados,
   depois de revisão, viram exemplos (python -m agente.promover_feedback).

Recuperação por sobreposição de radicais (sem acento, minúsculo, 5 primeiras
letras), ponderada por raridade (IDF). Com dezenas de exemplos isso basta e
não exige modelo de embedding nem chamada extra à API.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import yaml

from consumo import dados

RAIZ = Path(__file__).resolve().parent.parent
ARQ_EXEMPLOS = Path(__file__).parent / "exemplos_verificados.yaml"
ARQ_FEEDBACK = RAIZ / "data" / "agente" / "feedback.jsonl"

_VAZIAS = {
    "quais",
    "qual",
    "quant",
    "quantos",
    "quantas",
    "como",
    "onde",
    "porqu",
    "para",
    "com",
    "sem",
    "que",
    "dos",
    "das",
    "uma",
    "por",
    "mais",
    "menos",
    "tem",
    "existe",
    "exist",
    "estao",
    "esta",
    "sao",
    "the",
    "nos",
    "nas",
}


def _radicais(texto: str) -> list[str]:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    palavras = re.findall(r"[a-z0-9]+", t)
    return [p[:5] for p in palavras if len(p) > 2 and p[:5] not in _VAZIAS]


@lru_cache(maxsize=1)
def exemplos() -> list[dict]:
    return yaml.safe_load(ARQ_EXEMPLOS.read_text(encoding="utf-8"))["exemplos"]


@lru_cache(maxsize=1)
def _indice() -> tuple[list[set[str]], dict[str, float]]:
    docs = [set(_radicais(e["pergunta"] + " " + e.get("nota", ""))) for e in exemplos()]
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for r in d:
            df[r] = df.get(r, 0) + 1
    idf = {r: math.log((n + 1) / (c + 0.5)) for r, c in df.items()}
    return docs, idf


def exemplos_parecidos(pergunta: str, k: int = 3) -> list[dict]:
    docs, idf = _indice()
    q = set(_radicais(pergunta))
    pontuados = []
    for e, d in zip(exemplos(), docs, strict=True):
        comum = q & d
        if not comum:
            continue
        pontuados.append((sum(idf.get(r, 0) for r in comum) / math.sqrt(len(d) + 1), e))
    pontuados.sort(key=lambda p: p[0], reverse=True)
    return [e for _, e in pontuados[:k]]


@lru_cache(maxsize=1)
def catalogo_compacto() -> str:
    linhas = []
    for nome, m in sorted(dados.catalogo().get("modelos", {}).items()):
        colunas = ", ".join(list(m["colunas"])[:28])
        descricao = m["descricao"].split(". ")[0][:160]
        linhas.append(f"- publicado.{nome}: {descricao}. Colunas: {colunas}")
    return "\n".join(linhas)


def bloco_para_prompt(pergunta: str) -> str:
    partes = [
        "Tabelas disponíveis (use descrever_tabela só se precisar de tipos ou de uma coluna que não está aqui):",
        catalogo_compacto(),
    ]
    parecidos = exemplos_parecidos(pergunta)
    if parecidos:
        partes.append("\nExemplos verificados de perguntas parecidas (siga o padrão; adapte filtros e colunas):")
        for e in parecidos:
            nota = f"\n  -- {e['nota']}" if e.get("nota") else ""
            partes.append(f"P: {e['pergunta']}{nota}\n  SQL: {' '.join(e['sql'].split())}")
    return "\n".join(partes)


def registrar_feedback(pergunta: str, resposta: str, sqls: list[str], util: bool, comentario: str = "") -> bool:
    """Grava o feedback. Em ambiente sem disco gravável (Vercel) só registra em log e devolve False."""
    linha = {
        "em": datetime.now(UTC).isoformat(timespec="seconds"),
        "pergunta": pergunta[:1000],
        "resposta": resposta[:4000],
        "sqls": sqls[:5],
        "util": util,
        "comentario": comentario[:500],
    }
    try:
        ARQ_FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
        with ARQ_FEEDBACK.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        return True
    except OSError:
        import logging

        logging.getLogger(__name__).info("feedback (sem disco): %s", json.dumps(linha, ensure_ascii=False))
        return False
