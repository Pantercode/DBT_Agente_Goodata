"""Revisão do feedback do chat: transforma respostas aprovadas em exemplos verificados.

    python -m agente.promover_feedback            # lista candidatos (👍 com SQL que ainda roda)
    python -m agente.promover_feedback --gravar   # acrescenta os candidatos ao YAML

Só entra o que: recebeu 👍, tem ao menos um SQL, o SQL ainda passa na guarda e
roda hoje, e a pergunta não é parecida demais com um exemplo que já existe.
O resultado é um diff no YAML para revisão em PR; nada entra direto.
"""

from __future__ import annotations

import argparse
import json
import sys

import yaml

from agente import memoria
from agente.guarda_sql import SQLRecusado, validar
from consumo import dados


def candidatos() -> list[dict]:
    if not memoria.ARQ_FEEDBACK.exists():
        return []
    existentes = {e["pergunta"].lower() for e in memoria.exemplos()}
    tabelas = set(dados.tabelas())
    saida = []
    for linha in memoria.ARQ_FEEDBACK.read_text(encoding="utf-8").splitlines():
        fb = json.loads(linha)
        if not fb["util"] or not fb["sqls"] or fb["pergunta"].lower() in existentes:
            continue
        if memoria.exemplos_parecidos(fb["pergunta"], k=1) and set(memoria._radicais(fb["pergunta"])) <= set(
            memoria._radicais(memoria.exemplos_parecidos(fb["pergunta"], k=1)[0]["pergunta"])
        ):
            continue
        sql = fb["sqls"][-1]
        try:
            dados.consultar(validar(sql, tabelas).sql)
        except (SQLRecusado, Exception):
            continue
        saida.append({"pergunta": fb["pergunta"], "sql": sql, "nota": "aprovado pelo usuário no chat"})
        existentes.add(fb["pergunta"].lower())
    return saida


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="agente.promover_feedback")
    p.add_argument("--gravar", action="store_true")
    args = p.parse_args()
    novos = candidatos()
    for n in novos:
        print(f"+ {n['pergunta']}\n    {n['sql']}")
    if not novos:
        print("nenhum candidato novo")
    if args.gravar and novos:
        doc = yaml.safe_load(memoria.ARQ_EXEMPLOS.read_text(encoding="utf-8"))
        cabecalho = memoria.ARQ_EXEMPLOS.read_text(encoding="utf-8").split("exemplos:")[0]
        doc["exemplos"].extend(novos)
        corpo = yaml.safe_dump({"exemplos": doc["exemplos"]}, allow_unicode=True, sort_keys=False, width=110)
        memoria.ARQ_EXEMPLOS.write_text(cabecalho + corpo, encoding="utf-8")
        print(f"{len(novos)} exemplo(s) gravado(s). Revise o diff antes de commitar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
