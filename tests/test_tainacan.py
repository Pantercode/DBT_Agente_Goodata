from ingestao.tainacan import simplificar_item, simplificar_valor


def test_taxonomia_vira_id_nome_pai():
    valor = {"name": "Aberto", "parent": 0, "taxonomy": "tnc_tax_270", "id": 24, "thumbnail": {"full": False}}
    assert simplificar_valor(valor) == {"id": 24, "nome": "Aberto", "pai": None}


def test_taxonomia_multivalorada():
    valor = [
        {"name": "Rampa", "taxonomy": "t", "id": 1, "parent": 0},
        {"name": "Elevador", "taxonomy": "t", "id": 2, "parent": 5},
    ]
    assert simplificar_valor(valor) == [
        {"id": 1, "nome": "Rampa", "pai": None},
        {"id": 2, "nome": "Elevador", "pai": 5},
    ]


def test_composto_guarda_so_metadatum_e_valor():
    valor = [
        {
            "metadatum_id": 2131,
            "value": "30000",
            "value_as_html": "<b>30000</b>",
            "value_as_string": "30000",
            "parent_meta_id": 9,
        }
    ]
    assert simplificar_valor(valor) == [{"metadatum_id": 2131, "valor": "30000"}]


def test_vazios_viram_none():
    # Tainacan usa false para taxonomia não preenchida
    assert simplificar_valor(False) is None
    assert simplificar_valor("") is None
    assert simplificar_valor([]) is None


def test_texto_passa_intacto():
    assert simplificar_valor("Sim") == "Sim"


def test_item_descarta_html():
    item = {
        "id": 1,
        "title": "Museu X",
        "description": "d",
        "creation_date": "01/02/2026",
        "modification_date": "03/02/2026",
        "url": "u",
        "metadata": {
            "uf": {"value": {"name": "MG", "taxonomy": "t", "id": 127, "parent": 0}, "value_as_html": "<a>MG</a>"}
        },
    }
    s = simplificar_item(item)
    assert s["item_id"] == 1
    assert s["metadados"] == {"uf": {"id": 127, "nome": "MG", "pai": None}}
    assert "value_as_html" not in str(s)
