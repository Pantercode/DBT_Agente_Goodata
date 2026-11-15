"""Uso:

python -m ingestao                 # todas as fontes, partição de hoje
python -m ingestao museus ibge     # só algumas
python -m ingestao --dt 2026-11-14 # força a data da partição (reprocessamento)
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from ingestao import ibge, tainacan
from ingestao.landing import RAIZ_LAKE, gravar_particao

RAIZ = Path(__file__).resolve().parent.parent
FONTES = ("museus", "pontos_memoria", "ibge")


def main() -> None:
    p = argparse.ArgumentParser(prog="ingestao")
    # Sem `choices` aqui: com nargs="*" o argparse valida o default inteiro como
    # se fosse um único valor e rejeita a lista.
    p.add_argument("fontes", nargs="*", help=f"subconjunto de {', '.join(FONTES)} (padrão: todas)")
    p.add_argument("--dt", type=date.fromisoformat, default=date.today())
    p.add_argument("--raiz", type=Path, default=RAIZ_LAKE)
    args = p.parse_args()
    args.fontes = args.fontes or list(FONTES)
    if invalidas := set(args.fontes) - set(FONTES):
        p.error(f"fontes desconhecidas: {', '.join(sorted(invalidas))}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("ingestao")
    manifests = []

    for nome in ("museus", "pontos_memoria"):
        if nome not in args.fontes:
            continue
        colecao = tainacan.COLECOES[nome]
        itens, metadados, total, dur = tainacan.extrair_colecao(colecao)
        if total and len(itens) < total * 0.98:
            # Não grava partição incompleta: o dbt continuaria com a de ontem.
            raise SystemExit(f"{nome}: extraídos {len(itens)} de {total} itens, abaixo de 98%. Abortando.")
        manifests.append(
            gravar_particao(
                "tainacan",
                colecao.entidade,
                itens,
                args.dt,
                total_origem=total,
                duracao_s=dur,
                parametros={"colecao_id": colecao.id},
                raiz=args.raiz,
            )
        )
        manifests.append(
            gravar_particao("tainacan", f"{colecao.entidade}_metadados", metadados, args.dt, raiz=args.raiz)
        )

    if "ibge" in args.fontes:
        municipios, dur = ibge.extrair_municipios()
        manifests.append(gravar_particao("ibge", "municipios", municipios, args.dt, duracao_s=dur, raiz=args.raiz))
        populacao, dur = ibge.extrair_populacao()
        manifests.append(gravar_particao("ibge", "populacao", populacao, args.dt, duracao_s=dur, raiz=args.raiz))
        ibge.baixar_malha_uf(RAIZ / "data" / "serving" / "malha_uf.geojson")

    for m in manifests:
        log.info(
            "%s/%s dt=%s: %s registros (origem informa %s) em %ss",
            m.fonte,
            m.entidade,
            m.dt,
            m.registros,
            m.total_informado_pela_origem,
            m.duracao_s,
        )
    print(json.dumps([m.__dict__ for m in manifests], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
