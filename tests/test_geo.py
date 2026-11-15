from consumo.geo import _area_assinada, orientar_para_d3

ANTI_HORARIO = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]  # área positiva


def test_anel_externo_fica_horario():
    gj = {"features": [{"geometry": {"type": "Polygon", "coordinates": [ANTI_HORARIO]}}]}
    anel = orientar_para_d3(gj)["features"][0]["geometry"]["coordinates"][0]
    assert _area_assinada(anel) < 0


def test_buraco_fica_anti_horario():
    buraco_horario = ANTI_HORARIO[::-1]
    gj = {"features": [{"geometry": {"type": "Polygon", "coordinates": [ANTI_HORARIO, buraco_horario]}}]}
    externo, buraco = orientar_para_d3(gj)["features"][0]["geometry"]["coordinates"]
    assert _area_assinada(externo) < 0
    assert _area_assinada(buraco) > 0


def test_multipolygon():
    gj = {"features": [{"geometry": {"type": "MultiPolygon", "coordinates": [[ANTI_HORARIO], [ANTI_HORARIO]]}}]}
    for poligono in orientar_para_d3(gj)["features"][0]["geometry"]["coordinates"]:
        assert _area_assinada(poligono[0]) < 0
