"""Modelo lógico (LDM) do GoodData declarado em código.

Por que não usar o gerador automático (scan + generate_logical_model): os IDs
gerados dependem de convenção de nome de coluna e mudam se a coluna mudar. As
métricas MAQL e os dashboards referenciam esses IDs; ID instável quebra
dashboard em produção. Aqui o ID é decidido uma vez e revisado em PR.

A especificação é compacta (DATASETS) e `ldm()` a expande para o formato
declarativo da API.
"""

from __future__ import annotations

from gooddata_sdk import CatalogDeclarativeModel

TIPOS = {"int": "INT", "txt": "STRING", "num": "NUMERIC", "data": "DATE"}

# (coluna, título, tipo). A primeira coluna de `atributos` é a grain.
DATASETS = {
    "municipio": {
        "tabela": "gd_municipio",
        "titulo": "Município",
        "atributos": [
            ("municipio_id", "Código IBGE do município", "int"),
            ("municipio_rotulo", "Município", "txt"),
            ("uf_sigla", "UF", "txt"),
            ("regiao_nome", "Região", "txt"),
            ("faixa_populacional", "Porte do município", "txt"),
            ("classe_cobertura", "Cobertura museal", "txt"),
        ],
        "fatos": [
            ("populacao", "População", "int"),
            ("qtd_museus_ativos", "Museus ativos no município", "int"),
            ("tem_museu_ativo", "Tem museu ativo (0/1)", "int"),
            ("populacao_sem_museu", "População sem museu", "int"),
        ],
        "referencias": [],
    },
    "museu": {
        "tabela": "gd_museu",
        "titulo": "Museu",
        "atributos": [
            ("museu_id", "ID do museu", "int"),
            ("nome_museu", "Museu", "txt"),
            ("tipo_museu", "Tipo de museu", "txt"),
            ("tematica", "Temática", "txt"),
            ("status_funcionamento", "Status de funcionamento", "txt"),
            ("natureza_administrativa", "Natureza administrativa", "txt"),
            ("perfil_administrativo", "Perfil administrativo", "txt"),
            ("faixa_gestao", "Faixa de gestão", "txt"),
            ("decada_abertura", "Década de abertura", "txt"),
        ],
        "fatos": [
            ("is_aberto", "Ativo (0/1)", "int"),
            ("indice_gestao", "Índice de gestão", "int"),
            ("indice_gestao_se_ativo", "Índice de gestão (só ativos)", "int"),
            ("possui_plano_museologico", "Tem plano museológico (0/1)", "int"),
            ("respondeu_plano_museologico", "Respondeu sobre plano (0/1)", "int"),
            ("dimensoes_acessibilidade", "Dimensões de acessibilidade", "int"),
            ("sem_acessibilidade", "Sem acessibilidade (0/1)", "int"),
            ("qtd_pessoas_trabalham", "Pessoas trabalhando", "int"),
            ("qtd_bens_culturais", "Bens culturais", "int"),
        ],
        # (coluna local, dataset alvo)
        "referencias": [("municipio_id", "municipio")],
    },
}


def ldm(data_source_id: str, schema: str | None) -> CatalogDeclarativeModel:
    """`schema` None = armazenamento gerenciado do GoodData (GDSTORAGE), onde a tabela não tem schema."""
    datasets = []
    for ds_id, spec in DATASETS.items():
        grain_col = spec["atributos"][0][0]
        datasets.append(
            {
                "id": ds_id,
                "title": spec["titulo"],
                "grain": [{"id": f"{ds_id}.{grain_col}", "type": "attribute"}],
                "dataSourceTableId": {
                    "dataSourceId": data_source_id,
                    "id": spec["tabela"],
                    "type": "dataSource",
                    "path": [schema, spec["tabela"]] if schema else [spec["tabela"]],
                },
                "attributes": [
                    {
                        "id": f"{ds_id}.{col}",
                        "title": titulo,
                        "sourceColumn": col,
                        "sourceColumnDataType": TIPOS[tipo],
                        "labels": [],
                        "tags": [spec["titulo"]],
                    }
                    for col, titulo, tipo in spec["atributos"]
                ],
                "facts": [
                    {
                        "id": f"{ds_id}.{col}",
                        "title": titulo,
                        "sourceColumn": col,
                        "sourceColumnDataType": TIPOS[tipo],
                        "tags": [spec["titulo"]],
                    }
                    for col, titulo, tipo in spec["fatos"]
                ],
                "references": [
                    {
                        "identifier": {"id": alvo, "type": "dataset"},
                        "multivalue": False,
                        "sources": [
                            {
                                "column": col,
                                "dataType": "INT",
                                "target": {"id": f"{alvo}.{DATASETS[alvo]['atributos'][0][0]}", "type": "attribute"},
                            }
                        ],
                    }
                    for col, alvo in spec["referencias"]
                ],
                "tags": [spec["titulo"]],
            }
        )
    return CatalogDeclarativeModel.from_dict({"ldm": {"datasets": datasets, "dateInstances": []}})


def ids_validos() -> set[str]:
    """Todos os {fact/...}, {attribute/...} e {label/...} que o MAQL pode citar."""
    ids = set()
    for ds_id, spec in DATASETS.items():
        for col, *_ in spec["atributos"]:
            ids |= {f"attribute/{ds_id}.{col}", f"label/{ds_id}.{col}"}
        for col, *_ in spec["fatos"]:
            ids.add(f"fact/{ds_id}.{col}")
    return ids
