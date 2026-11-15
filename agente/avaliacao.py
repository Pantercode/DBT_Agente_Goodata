"""Avaliação do agente contra respostas conferidas por SQL.

    python -m agente.avaliacao              # roda todas as perguntas
    python -m agente.avaliacao --n 4        # só as 4 primeiras (free tier tem cota por minuto)

Cada caso tem uma pergunta e um SQL de gabarito. O gabarito roda na hora
(então a avaliação acompanha os dados), e o número esperado é procurado na
resposta do agente em formato brasileiro, com tolerância de arredondamento.

Métricas:
  acerto        o número do gabarito aparece na resposta
  cita_fonte    a resposta termina citando a tabela ("Fonte:")
  passos        quantas ferramentas foram chamadas (menos é melhor, com acerto igual)

O resultado vai para data/agente/avaliacao.json, com data e modelo, para
comparar uma mudança de prompt ou de exemplos com a anterior.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

CASOS = [
    {
        "pergunta": "Quantos museus ativos existem no Brasil?",
        "gabarito": "select qtd_museus_ativos as v from publicado.agg_cobertura_brasil",
        "casas": 0,
    },
    {
        "pergunta": "Qual UF tem menos museus por 100 mil habitantes e qual é esse número?",
        "gabarito": "select museus_por_100k_hab as v from publicado.agg_cobertura_uf order by 1 limit 1",
        "casas": 2,
    },
    {
        "pergunta": "Quantos museus por 100 mil habitantes tem a região Sul, considerando a região inteira?",
        "gabarito": "select sum(qtd_museus_ativos) * 100000.0 / sum(populacao) as v from publicado.agg_cobertura_uf where regiao_sigla = 'S'",
        "casas": 2,
    },
    {
        "pergunta": "Qual a população da maior cidade do Brasil sem nenhum museu ativo?",
        "gabarito": "select populacao as v from publicado.agg_cobertura_municipio where not tem_museu_ativo order by 1 desc limit 1",
        "casas": 0,
    },
    {
        "pergunta": "Quantos museus ativos não têm nenhum recurso de acessibilidade?",
        "gabarito": "select count(*) as v from publicado.obt_museus where is_aberto and acessibilidade.dimensoes_atendidas = 0",
        "casas": 0,
    },
    {
        "pergunta": "Quantos museus comunitários ativos existem na Bahia?",
        "gabarito": """select count(*) as v from publicado.obt_museus o join publicado.dim_museu d
                    on d.museu_id = o.museu_id and d.is_versao_atual
                    where o.uf_sigla = 'BA' and o.is_aberto and d.is_comunitario""",
        "casas": 0,
    },
    {
        "pergunta": "Em que década foram abertos mais museus que existem hoje, e quantos?",
        "gabarito": "select sum(qtd_museus) as v from publicado.agg_aberturas_por_decada group by decada_abertura order by 1 desc limit 1",
        "casas": 0,
    },
    {
        "pergunta": "Que percentual da população do Nordeste mora em município sem museu?",
        "gabarito": "select sum(populacao_sem_museu) * 100.0 / sum(populacao) as v from publicado.agg_cobertura_uf where regiao_sigla = 'NE'",
        "casas": 1,
    },
]


def _formatos(valor: float, casas: int) -> set[str]:
    """Formas aceitas do número na resposta: 1.018 / 1018 / 1,55 / 1.55 / 46,9 / 47 (arredondado)."""
    saida = set()
    for c in {casas, max(casas - 1, 0)}:
        br = f"{valor:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        saida |= {br, br.replace(".", ""), f"{valor:.{c}f}"}
    return saida


def avaliar(n: int | None = None, pausa_s: float = 4.0) -> dict:
    from agente.nucleo import AgenteIndisponivel, perguntar
    from consumo.dados import consultar

    resultados = []
    for caso in CASOS[:n]:
        esperado = float(consultar(caso["gabarito"])[0]["v"])
        formatos = _formatos(esperado, caso["casas"])
        inicio = time.monotonic()
        try:
            r = perguntar(caso["pergunta"])
            texto, passos, modelo, erro = r.texto, len(r.passos), r.modelo, None
        except AgenteIndisponivel as exc:
            texto, passos, modelo, erro = "", 0, None, str(exc)
        limpo = re.sub(r"\*\*", "", texto)
        acerto = any(f in limpo for f in formatos)
        resultados.append(
            {
                "pergunta": caso["pergunta"],
                "esperado": esperado,
                "acerto": acerto,
                "cita_fonte": "fonte:" in limpo.lower(),
                "passos": passos,
                "modelo": modelo,
                "segundos": round(time.monotonic() - inicio, 1),
                "erro": erro,
                "trecho": limpo[:240].replace("\n", " "),
            }
        )
        marca = "OK " if acerto else ("ERRO" if erro else "x  ")
        print(f"{marca} {caso['pergunta'][:70]:<70} esperado {esperado:g}  passos {passos}")
        time.sleep(pausa_s)

    validos = [r for r in resultados if not r["erro"]]
    resumo = {
        "em": datetime.now(UTC).isoformat(timespec="seconds"),
        "casos": len(resultados),
        "acerto": round(sum(r["acerto"] for r in validos) / max(len(validos), 1), 3),
        "cita_fonte": round(sum(r["cita_fonte"] for r in validos) / max(len(validos), 1), 3),
        "passos_medios": round(sum(r["passos"] for r in validos) / max(len(validos), 1), 2),
        "erros_de_api": len(resultados) - len(validos),
        "resultados": resultados,
    }
    destino = RAIZ / "data" / "agente" / "avaliacao.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo


def main() -> int:
    load_dotenv(RAIZ / ".env")
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="agente.avaliacao")
    p.add_argument("--n", type=int)
    args = p.parse_args()
    r = avaliar(args.n)
    print(
        f"\nacerto {r['acerto']:.0%} · cita fonte {r['cita_fonte']:.0%} · {r['passos_medios']} passos em média"
        f" · {r['erros_de_api']} erro(s) de API"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
