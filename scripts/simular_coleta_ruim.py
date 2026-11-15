"""Grava no lake uma partição de museus "quebrada", para ver a quarentena funcionando.

    python scripts/simular_coleta_ruim.py 2026-11-15          # cria
    python -m orquestracao.pipeline --sem-ingestao            # roda: a partição vai para quarentena
    python scripts/simular_coleta_ruim.py 2026-11-15 --apagar # remove a simulação

Simula o caso que passa pela checagem da ingestão: a própria API devolveu
metade dos itens e informou esse total menor (então "extraídos / informados"
dá 100%), e 300 itens vieram sem UF. A ingestão não tem como saber que está
errado; a validação de partição no dbt tem (volume contra as partições
anteriores, completude).
"""

from __future__ import annotations

import gzip
import json
import random
import shutil
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ingestao.landing import RAIZ_LAKE, caminho_particao, gravar_particao  # noqa: E402


def main() -> None:
    dt = date.fromisoformat(sys.argv[1])
    if "--apagar" in sys.argv:
        shutil.rmtree(caminho_particao("tainacan", "museus", dt))
        print("partição simulada removida:", dt)
        return

    base = sorted(p for p in (RAIZ_LAKE / "tainacan" / "museus").glob("dt=*") if p.name != f"dt={dt}")[-1]
    with gzip.open(base / "part-0000.jsonl.gz", "rt", encoding="utf-8") as fh:
        itens = [{k: v for k, v in json.loads(linha).items() if k != "_extraido_em"} for linha in fh]

    rng = random.Random(7)
    metade = rng.sample(itens, len(itens) // 2)
    for item in rng.sample(metade, 300):
        item["metadados"]["uf"] = None
    m = gravar_particao("tainacan", "museus", metade, dt, total_origem=len(metade), parametros={"simulacao": True})
    print(f"partição simulada dt={dt}: {m.registros} itens (a anterior tinha {len(itens)}), 300 sem UF")


if __name__ == "__main__":
    main()
