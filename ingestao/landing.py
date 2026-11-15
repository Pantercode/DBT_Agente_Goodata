"""Escrita no landing zone.

Layout (estilo Hive, para o DuckDB/BigQuery lerem com partition pruning):

    data/lake/raw/<fonte>/<entidade>/dt=YYYY-MM-DD/part-0000.jsonl.gz
    data/lake/raw/<fonte>/<entidade>/dt=YYYY-MM-DD/_manifest.json

Regras:
- Uma partição por data de extração. Reextrair no mesmo dia sobrescreve a
  partição inteira (idempotente); dias anteriores nunca são tocados.
- Escreve em diretório temporário e renomeia no final, para que o dbt nunca leia
  uma partição pela metade.
- O manifest guarda contagem, hash e duração. O dbt usa a contagem para o teste
  de reconciliação origem x staging.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

RAIZ_LAKE = Path(__file__).resolve().parent.parent / "data" / "lake" / "raw"


@dataclass
class Manifest:
    fonte: str
    entidade: str
    dt: str
    extraido_em: str
    registros: int
    total_informado_pela_origem: int | None
    sha256: str
    duracao_s: float
    parametros: dict = field(default_factory=dict)


def caminho_particao(fonte: str, entidade: str, dt: date, raiz: Path = RAIZ_LAKE) -> Path:
    return raiz / fonte / entidade / f"dt={dt.isoformat()}"


def gravar_particao(
    fonte: str,
    entidade: str,
    registros: list[dict],
    dt: date,
    *,
    total_origem: int | None = None,
    duracao_s: float = 0.0,
    parametros: dict | None = None,
    raiz: Path = RAIZ_LAKE,
) -> Manifest:
    destino = caminho_particao(fonte, entidade, dt, raiz)
    tmp = destino.with_name(destino.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    extraido_em = datetime.now(UTC).isoformat(timespec="seconds")
    sha = hashlib.sha256()
    with gzip.open(tmp / "part-0000.jsonl.gz", "wt", encoding="utf-8") as fh:
        for reg in registros:
            # _extraido_em vai em cada linha: é o loaded_at_field do source freshness.
            linha = json.dumps({**reg, "_extraido_em": extraido_em}, ensure_ascii=False, sort_keys=True)
            sha.update(linha.encode())
            fh.write(linha + "\n")

    manifest = Manifest(
        fonte=fonte,
        entidade=entidade,
        dt=dt.isoformat(),
        extraido_em=extraido_em,
        registros=len(registros),
        total_informado_pela_origem=total_origem,
        sha256=sha.hexdigest(),
        duracao_s=round(duracao_s, 1),
        parametros=parametros or {},
    )
    (tmp / "_manifest.json").write_text(json.dumps(asdict(manifest), indent=2, ensure_ascii=False), encoding="utf-8")

    if destino.exists():
        shutil.rmtree(destino)
    tmp.rename(destino)
    return manifest
