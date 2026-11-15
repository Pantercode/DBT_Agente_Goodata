"""Gera tests/fixtures/lake: uma amostra do lake real para o CI rodar `dbt build` sem rede.

    python scripts/gerar_fixture_ci.py

Amostra estratificada por UF (até 15 museus e 3 pontos de memória por UF),
IBGE completo. Três partições de museus: a segunda com um museu fechado e outro removido
(o SCD2 tem história de verdade) e a terceira quebrada (tem que ir para quarentena).
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

from ingestao.landing import RAIZ_LAKE, gravar_particao  # noqa: E402

DESTINO = RAIZ / "tests" / "fixtures" / "lake"
D1, D2, D3 = date(2026, 11, 13), date(2026, 11, 14), date(2026, 11, 15)


def _ler(fonte: str, entidade: str) -> list[dict]:
    particao = sorted((RAIZ_LAKE / fonte / entidade).glob("dt=*"))[-1]
    with gzip.open(particao / "part-0000.jsonl.gz", "rt", encoding="utf-8") as fh:
        return [{k: v for k, v in json.loads(linha).items() if k != "_extraido_em"} for linha in fh]


def _amostra_por_uf(itens: list[dict], chave_uf: str, n: int) -> list[dict]:
    por_uf: dict[str, list[dict]] = {}
    for item in itens:
        uf = ((item["metadados"].get(chave_uf) or {}) or {}).get("nome")
        por_uf.setdefault(uf, []).append(item)
    # Sem UF fica de fora: na base inteira são 0,6%, mas numa amostra de 80 viram 4%
    # e o teste de cobertura (que vale para a base real) falharia por artefato da amostra.
    por_uf.pop(None, None)
    rng = random.Random(42)
    return sorted(
        (i for grupo in por_uf.values() for i in rng.sample(grupo, min(n, len(grupo)))), key=lambda i: i["item_id"]
    )


def main() -> None:
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    museus = _amostra_por_uf(_ler("tainacan", "museus"), "uf", 15)
    pontos = _amostra_por_uf(_ler("tainacan", "pontos_memoria"), "estado", 3)

    gravar_particao("tainacan", "museus", museus, D1, total_origem=len(museus), raiz=DESTINO)
    dia2 = [json.loads(json.dumps(m)) for m in museus[1:]]  # o primeiro some do cadastro
    # e um museu aberto fecha (tem que estar aberto no dia 1, senão não há mudança)
    aberto = next(m for m in dia2 if (m["metadados"].get("mus_status") or {}).get("nome") == "Aberto")
    aberto["metadados"]["mus_status"] = {"id": 0, "nome": "Fechado", "pai": None}
    gravar_particao("tainacan", "museus", dia2, D2, total_origem=len(dia2), raiz=DESTINO)

    # Dia 3: coleta quebrada (metade dos itens, 20% sem UF). Tem que ir para
    # quarentena, e os marts têm que continuar com o dia 2.
    quebrada = [json.loads(json.dumps(m)) for m in dia2[: len(dia2) // 2]]
    for m in quebrada[: len(quebrada) // 5]:
        m["metadados"]["uf"] = None
    gravar_particao("tainacan", "museus", quebrada, D3, total_origem=len(quebrada), raiz=DESTINO)

    for dt in (D1, D2):
        gravar_particao("tainacan", "pontos_memoria", pontos, dt, total_origem=len(pontos), raiz=DESTINO)
    for entidade in ("museus_metadados", "pontos_memoria_metadados"):
        gravar_particao("tainacan", entidade, _ler("tainacan", entidade), D2, raiz=DESTINO)
    for entidade in ("municipios", "populacao"):
        gravar_particao("ibge", entidade, _ler("ibge", entidade), D2, raiz=DESTINO)
    print(f"{len(museus)} museus, {len(pontos)} pontos de memória em {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
