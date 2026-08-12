from pathlib import Path

from sieej_datalayer.models import EstadoFuente
from sieej_datalayer.static_docs import escanear_html, escanear_views_md

FIXTURES = Path(__file__).parent / "fixtures"


def test_escanear_html_excluye_index_y_aplica_alias():
    fuente, docs = escanear_html(FIXTURES / "html-documents")
    assert fuente.estado is EstadoFuente.OK
    assert set(docs) == {"denue", "conapo", "censo_economico"}
    assert docs["denue"].titulo.startswith("DENUE")
    assert docs["censo_economico"].archivo == "censos_economicos.html"


def test_escanear_html_sin_configurar_y_caida():
    fuente, docs = escanear_html(None)
    assert fuente.estado is EstadoFuente.SIN_CONFIGURAR and docs == {}
    fuente, docs = escanear_html(FIXTURES / "no-existe")
    assert fuente.estado is EstadoFuente.CAIDA and docs == {}


def test_escanear_views_md_parsea_columnas_y_tipo():
    fuente, por_bd = escanear_views_md(FIXTURES / "views-md")
    assert fuente.estado is EstadoFuente.OK
    assert set(por_bd) == {"denue", "fiscalia"}

    vista = por_bd["denue"][0]
    assert vista.nombre == "v_establecimientos"
    assert vista.tipo == "VIEW"
    assert vista.registros is None  # -1 en el markdown = desconocido
    assert vista.en_docs is True
    assert [c.nombre for c in vista.columnas] == ["id", "nombre_establecimiento", "latitud"]
    assert vista.columnas[0].nullable is False
    assert vista.columnas[2].tipo == "double precision"

    matview = por_bd["fiscalia"][0]
    assert matview.tipo == "MATERIALIZED VIEW"
    assert matview.registros == 3200
    assert matview.archivo_md == "fiscalia__public__delitos_vw.md"
