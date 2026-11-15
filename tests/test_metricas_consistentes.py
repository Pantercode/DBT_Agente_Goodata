"""As métricas `core` precisam existir com o mesmo nome no dbt Semantic Layer e
no GoodData, e estar documentadas em docs/metricas.md. É o teste que segura a
"consistência absoluta de KPI" entre ferramentas."""

from pathlib import Path

import yaml

from gooddata.provisionar import metricas, validar_maql

RAIZ = Path(__file__).resolve().parent.parent


def _metricas_dbt() -> set[str]:
    yml = yaml.safe_load((RAIZ / "dbt/models/semantic/semantic_models.yml").read_text(encoding="utf-8"))
    return {m["name"] for m in yml["metrics"]}


def _metricas_gooddata_core() -> set[str]:
    return {m["id"] for m in metricas() if m.get("core")}


def test_maql_so_referencia_ids_do_modelo_logico():
    assert validar_maql() == []


def test_core_do_gooddata_existe_no_dbt_ou_em_mart():
    # museus_por_100k_hab, pct_* de cobertura são colunas de mart (agg_cobertura_*),
    # não métricas do semantic layer (dependem de denominador de outra tabela).
    colunas_mart = {"museus_por_100k_hab", "pct_municipios_com_museu", "pct_populacao_sem_museu"}
    faltando = _metricas_gooddata_core() - _metricas_dbt() - colunas_mart
    assert not faltando, f"métricas core do GoodData sem par no dbt: {faltando}"


def test_metricas_core_documentadas():
    doc = (RAIZ / "docs/metricas.md").read_text(encoding="utf-8")
    faltando = {m for m in _metricas_gooddata_core() if f"`{m}`" not in doc}
    assert not faltando, f"documente em docs/metricas.md: {faltando}"
