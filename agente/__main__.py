"""python -m agente "Quais UFs têm menos museus por habitante?" [--rastro]"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from agente.nucleo import AgenteIndisponivel, perguntar


def main() -> int:
    load_dotenv(".env")
    p = argparse.ArgumentParser(prog="agente")
    p.add_argument("pergunta")
    p.add_argument("--rastro", action="store_true", help="mostra ferramentas chamadas e SQL")
    p.add_argument("--modelo")
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING)
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        r = perguntar(args.pergunta, modelo=args.modelo)
    except AgenteIndisponivel as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    if args.rastro:
        for i, passo in enumerate(r.passos, 1):
            print(f"[{i}] {passo.ferramenta}({passo.argumentos}) {passo.duracao_ms}ms{' ERRO' if passo.erro else ''}")
            if passo.sql:
                print(f"    {passo.sql}")
        print(f"--- {r.modelo}, {r.iteracoes} iterações, {r.tokens_entrada}+{r.tokens_saida} tokens\n")
    print(r.texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
