"""Pipeline diário: ingestão -> freshness -> build (write+audit) -> circuit breaker -> publish -> serving.

    python -m orquestracao.pipeline                 # tudo
    python -m orquestracao.pipeline --sem-ingestao  # usa o lake que já existe
    python -m orquestracao.pipeline --so-exportar   # só regera data/serving a partir de `publicado`

Cada etapa que falha interrompe as seguintes. O estado da execução vai para
data/serving/status_pipeline.json, que o painel mostra na aba Qualidade.

Por que um script e não Airflow/Dagster: são seis passos lineares, uma vez por
dia. O desenho (etapas idempotentes, estado em arquivo, código de saída por
etapa) é o mesmo que iria para um DAG; ver docs/decisoes/005.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from orquestracao import serving

RAIZ = Path(__file__).resolve().parent.parent
DBT_DIR = RAIZ / "dbt"
STATUS = RAIZ / "data" / "serving" / "status_pipeline.json"

log = logging.getLogger("pipeline")


class CircuitBreaker(RuntimeError):
    """Falha de qualidade que impede a publicação."""


@dataclass
class Etapa:
    nome: str
    status: str = "pendente"
    duracao_s: float = 0.0
    detalhe: str = ""


@dataclass
class Execucao:
    iniciado_em: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    finalizado_em: str | None = None
    status: str = "em_andamento"
    publicou: bool = False
    etapas: list[Etapa] = field(default_factory=list)
    bloqueios: list[dict] = field(default_factory=list)
    avisos: list[dict] = field(default_factory=list)
    # partições que a validação mandou para quarentena nesta execução: os marts
    # seguem publicados com a última coleta coerente
    quarentena: list[dict] = field(default_factory=list)
    tempo_incrementais_s: dict = field(default_factory=dict)


def _dbt(*args: str) -> subprocess.CompletedProcess:
    exe = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    cmd = [str(exe), *args, "--profiles-dir", "."]
    log.info("$ dbt %s", " ".join(args))
    proc = subprocess.run(cmd, cwd=DBT_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for linha in proc.stdout.splitlines()[-15:]:
        log.info("  %s", linha)
    return proc


def _resultados_dbt() -> list[dict]:
    return json.loads((DBT_DIR / "target" / "run_results.json").read_text(encoding="utf-8"))["results"]


def _tags(unique_id: str) -> list[str]:
    manifest = json.loads((DBT_DIR / "target" / "manifest.json").read_text(encoding="utf-8"))
    no = manifest["nodes"].get(unique_id) or manifest.get("unit_tests", {}).get(unique_id) or {}
    return no.get("tags", [])


def _rodar(execucao: Execucao, nome: str, fn) -> None:
    etapa = Etapa(nome)
    execucao.etapas.append(etapa)
    inicio = time.monotonic()
    try:
        etapa.detalhe = fn() or ""
        etapa.status = "ok"
    except Exception as exc:
        etapa.status = "falhou"
        etapa.detalhe = str(exc)[:500]
        raise
    finally:
        etapa.duracao_s = round(time.monotonic() - inicio, 1)
        _gravar_status(execucao)


def _gravar_status(execucao: Execucao) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(asdict(execucao), ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------- etapas


def etapa_ingestao() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "ingestao"], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-800:])
    return "lake atualizado"


def etapa_freshness() -> str:
    proc = _dbt("source", "freshness")
    resultados = json.loads((DBT_DIR / "target" / "sources.json").read_text(encoding="utf-8"))["results"]
    atrasadas = [r["unique_id"] for r in resultados if r["status"] in ("error", "runtime error")]
    if atrasadas:
        # SLA de chegada estourado: publicar agora seria republicar dado velho como se fosse novo.
        raise CircuitBreaker(f"fontes fora do SLA: {', '.join(atrasadas)}")
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stdout[-800:])
    avisos = [r["unique_id"] for r in resultados if r["status"] == "warn"]
    return f"{len(resultados)} fontes checadas, {len(avisos)} em aviso"


def _bootstrap_se_preciso() -> None:
    """Primeira execução num warehouse vazio: o unit test do caminho incremental
    de dim_museu precisa da tabela existindo. Constrói ela (e o que vem antes) uma vez."""
    import duckdb

    arquivo = RAIZ / "data" / "warehouse" / "museus.duckdb"
    if arquivo.exists():
        with duckdb.connect(str(arquivo), read_only=True) as con:
            existe = con.execute(
                "select count(*) from information_schema.tables where table_schema = 'auditoria' and table_name = 'dim_museu'"
            ).fetchone()[0]
        if existe:
            return
    log.info("warehouse novo: bootstrap de dim_museu")
    _dbt("seed")
    _dbt("run", "--select", "+dim_museu")


def etapa_build(execucao: Execucao) -> str:
    _bootstrap_se_preciso()
    proc = _dbt("build")
    resultados = _resultados_dbt()
    for r in resultados:
        uid = r["unique_id"]
        if r["status"] in ("error", "fail", "skipped") and (
            r["status"] != "fail" or "bloqueante" in _tags(uid) or uid.startswith("unit_test.")
        ):
            execucao.bloqueios.append({"no": uid, "status": r["status"], "mensagem": (r.get("message") or "")[:300]})
        elif r["status"] in ("warn", "fail"):
            execucao.avisos.append({"no": uid, "status": r["status"], "falhas": r.get("failures")})
    if execucao.bloqueios:
        pulados = sum(1 for b in execucao.bloqueios if b["status"] == "skipped")
        causas = [
            b["no"].split(".")[-2] if b["no"].count(".") > 2 else b["no"]
            for b in execucao.bloqueios
            if b["status"] != "skipped"
        ]
        raise CircuitBreaker(
            f"{len(causas)} falha(s) bloqueante(s) ({', '.join(causas[:5])}); {pulados} nó(s) a jusante não rodaram"
        )
    if proc.returncode != 0 and not execucao.avisos:
        raise RuntimeError(proc.stdout[-800:])
    passou = sum(1 for r in resultados if r["status"] in ("pass", "success"))
    # Tempo de cada modelo incremental: cresce com as partições novas, não com o histórico.
    for r in resultados:
        nome = r["unique_id"].split(".")[-1]
        if nome in INCREMENTAIS and r["unique_id"].startswith("model."):
            execucao.tempo_incrementais_s[nome] = round(r["execution_time"], 2)
    execucao.quarentena = _particoes_em_quarentena()
    extra = f", {len(execucao.quarentena)} partição(ões) em quarentena" if execucao.quarentena else ""
    return f"{passou}/{len(resultados)} nós ok, {len(execucao.avisos)} aviso(s){extra}"


INCREMENTAIS = ("int_particoes__validacao", "int_museus__enriquecido", "dim_museu", "fct_museus_diario")


def _particoes_em_quarentena() -> list[dict]:
    """Partições mais novas que a que está em uso e que ficaram de fora."""
    import duckdb

    with duckdb.connect(str(RAIZ / "data" / "warehouse" / "museus.duckdb"), read_only=True) as con:
        linhas = con.execute(
            """
            select fonte, cast(dt as varchar), motivo_quarentena, cast(dt_em_uso as varchar)
            from auditoria.mart_saude_coleta
            where status = 'quarentena' and is_mais_nova_que_a_publicada
            order by dt desc
            """
        ).fetchall()
    return [{"fonte": f, "dt": d, "motivo": m, "dt_em_uso": u} for f, d, m, u in linhas]


def etapa_publicar(execucao: Execucao) -> str:
    proc = _dbt("run-operation", "publicar_marts")
    if proc.returncode != 0:
        # A macro tem o próprio breaker: se chegou aqui com erro, é bloqueio.
        raise CircuitBreaker(proc.stdout[-600:])
    execucao.publicou = True
    return "auditoria -> publicado"


def etapa_docs() -> str:
    proc = _dbt("docs", "generate")
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-500:])
    return "manifest + catalog"


def etapa_serving() -> str:
    arquivos = serving.exportar()
    return f"{len(arquivos)} arquivos em data/serving"


# ---------------------------------------------------------------------- main


def main() -> int:
    p = argparse.ArgumentParser(prog="pipeline")
    p.add_argument("--sem-ingestao", action="store_true")
    p.add_argument("--so-exportar", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    execucao = Execucao()
    try:
        if not args.so_exportar:
            if not args.sem_ingestao:
                _rodar(execucao, "ingestao", etapa_ingestao)
            _rodar(execucao, "freshness", etapa_freshness)
            _rodar(execucao, "build (write + audit)", lambda: etapa_build(execucao))
            _rodar(execucao, "publish", lambda: etapa_publicar(execucao))
            _rodar(execucao, "docs", etapa_docs)
        _rodar(execucao, "serving", etapa_serving)
        if execucao.quarentena:
            execucao.status = "sucesso_com_quarentena"
            for q in execucao.quarentena:
                log.warning(
                    "QUARENTENA %s dt=%s: %s. Publicado com dados de %s.",
                    q["fonte"],
                    q["dt"],
                    q["motivo"],
                    q["dt_em_uso"],
                )
        else:
            execucao.status = "sucesso_com_avisos" if execucao.avisos else "sucesso"
        return 0
    except CircuitBreaker as exc:
        execucao.status = "bloqueado"
        log.error("CIRCUIT BREAKER: %s. `publicado` mantém a versão anterior.", exc)
        return 2
    except Exception as exc:
        execucao.status = "falhou"
        log.exception("pipeline falhou: %s", exc)
        return 1
    finally:
        execucao.finalizado_em = datetime.now(UTC).isoformat(timespec="seconds")
        _gravar_status(execucao)


if __name__ == "__main__":
    raise SystemExit(main())
