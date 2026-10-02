from sieej_datalayer.respaldo import cargar_respaldo, svg_der


def test_el_respaldo_trae_tablas_con_filas_y_vistas_con_columnas():
    base, corte = cargar_respaldo("scian")
    assert corte == "27 de agosto de 2026"
    clases = next(t for t in base.tablas if t.nombre == "clases")
    assert clases.filas == 1086
    assert all(v.columnas for v in base.vistas)


def test_sin_respaldo_no_inventa_nada():
    assert cargar_respaldo("pipeline_que_no_existe") is None


def test_el_svg_se_limpia_y_gana_viewbox(tmp_path):
    carpeta = tmp_path / "core/pipelines/demo/assets"
    carpeta.mkdir(parents=True)
    (carpeta / "erd.svg").write_text(
        '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="300" '
        'height="120" onload="alert(1)"><script>alert(2)</script><rect/></svg>',
        encoding="utf-8",
    )
    svg = svg_der(tmp_path, "demo")
    assert svg.startswith('<svg viewBox="0 0 300 120" width="300"')
    assert "script" not in svg and "onload" not in svg
    assert svg_der(tmp_path, "otro") is None


def test_sin_erd_en_el_repo_se_usa_el_del_respaldo(tmp_path):
    svg = svg_der(tmp_path, "escuelas")
    assert svg.startswith('<svg viewBox="0 0 940.0 1020.0" width="940.0"')
    assert 'height="100%"' not in svg.split(">", 1)[0]
