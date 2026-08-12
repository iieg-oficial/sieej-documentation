from datetime import datetime, timezone

from sieej_datalayer.crosscheck import (
    construir_estructura_vistas,
    construir_inventario,
    construir_numeralia,
)
from sieej_datalayer.models import (
    BaseDeDatos,
    ClasificacionPipeline,
    Dag,
    DocumentacionHtml,
    EstadoFuente,
    Fuente,
    Vista,
)

AHORA = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _fuentes(airflow=EstadoFuente.OK, bd=EstadoFuente.OK) -> dict:
    return {
        "airflow": Fuente(estado=airflow),
        "bd": Fuente(estado=bd),
        "docs_html": Fuente(estado=EstadoFuente.OK),
        "views_md": Fuente(estado=EstadoFuente.OK),
    }


HTML = {
    "denue": DocumentacionHtml(archivo="denue.html", titulo="DENUE"),
    "conapo": DocumentacionHtml(archivo="conapo.html", titulo="CONAPO"),
}
VISTAS_DOCS = {
    "denue": [Vista(nombre="v_establecimientos", en_docs=True, archivo_md="x.md")],
    "cvegeo": [Vista(nombre="geometry_columns", en_docs=True)],
}
DAGS = {
    "etl_denue": Dag(dag_id="etl_denue", pausado=False),
    "etl_nuevo_pipeline": Dag(dag_id="etl_nuevo_pipeline", pausado=False),
}
BASES = [
    BaseDeDatos(
        nombre="denue",
        vistas=[
            Vista(nombre="v_establecimientos", en_bd=True),
            Vista(nombre="v_nueva", en_bd=True),
        ],
    ),
    BaseDeDatos(nombre="nuevo_pipeline", vistas=[Vista(nombre="v_algo", en_bd=True)]),
    BaseDeDatos(nombre="cvegeo", es_infraestructura=True, vistas=[]),
]


def test_clasificacion_con_fuentes_vivas():
    inv = construir_inventario(_fuentes(), HTML, VISTAS_DOCS, DAGS, BASES, AHORA)
    assert inv.pipelines["denue"].clasificacion is ClasificacionPipeline.DOCUMENTADO
    assert inv.pipelines["denue"].dag.dag_id == "etl_denue"
    assert inv.pipelines["denue"].vistas_en_bd == 2
    assert (
        inv.pipelines["nuevo_pipeline"].clasificacion
        is ClasificacionPipeline.DOCUMENTACION_PENDIENTE
    )
    assert inv.pipelines["conapo"].clasificacion is ClasificacionPipeline.POSIBLE_DESACTUALIZADO
    assert "nuevo_pipeline" in inv.cross_check["pipelines_sin_html"]
    assert inv.cross_check["html_sin_pipeline_vivo"] == ["conapo"]
    assert "cvegeo" not in inv.pipelines


def test_clasificacion_sin_fuentes_vivas():
    inv = construir_inventario(
        _fuentes(EstadoFuente.SIN_CONFIGURAR, EstadoFuente.SIN_CONFIGURAR),
        HTML,
        VISTAS_DOCS,
        {},
        [],
        AHORA,
    )
    assert all(
        p.clasificacion is ClasificacionPipeline.SIN_VERIFICAR for p in inv.pipelines.values()
    )
    assert inv.resumen["verificado_contra_produccion"] is False
    assert inv.pipelines["denue"].bd_existe is None


def test_numeralia_marca_discrepancias():
    inv = construir_inventario(_fuentes(), HTML, VISTAS_DOCS, DAGS, BASES, AHORA)
    num = construir_numeralia(_fuentes(), inv, DAGS, BASES, VISTAS_DOCS, AHORA)
    assert num.airflow["dags_activos"] == 2
    assert num.bd["bases_pipeline"] == 2
    assert num.documentacion["html_pipelines"] == 2
    assert num.cross_check["consistente"] is False
    assert any("pipelines_sin_html" in d for d in num.cross_check["discrepancias"])


def test_numeralia_consistente_sin_discrepancias():
    html = {"denue": HTML["denue"]}
    dags = {"etl_denue": DAGS["etl_denue"]}
    bases = [BASES[0], BASES[2]]
    vistas_docs = {"denue": VISTAS_DOCS["denue"], "cvegeo": VISTAS_DOCS["cvegeo"]}
    inv = construir_inventario(_fuentes(), html, vistas_docs, dags, bases, AHORA)
    num = construir_numeralia(_fuentes(), inv, dags, bases, vistas_docs, AHORA)
    cifras = num.cross_check["cifras"]
    assert cifras["pipelines_documentados"] == cifras["dags_activos"] == 1
    assert cifras["bases_con_vistas"] == 1
    assert num.cross_check["discrepancias"] == []
    assert num.cross_check["consistente"] is True


def test_estructura_vistas_cruza_bd_y_docs():
    est = construir_estructura_vistas(_fuentes(), BASES, VISTAS_DOCS, AHORA)
    denue = next(b for b in est.bases if b.nombre == "denue")
    por_nombre = {v.nombre: v for v in denue.vistas}
    assert por_nombre["v_establecimientos"].en_docs is True
    assert por_nombre["v_establecimientos"].solo_en_bd is False
    assert por_nombre["v_nueva"].solo_en_bd is True


def test_estructura_vistas_degrada_a_docs():
    est = construir_estructura_vistas(_fuentes(bd=EstadoFuente.CAIDA), [], VISTAS_DOCS, AHORA)
    assert {b.nombre for b in est.bases} == {"denue", "cvegeo"}
    denue = next(b for b in est.bases if b.nombre == "denue")
    assert denue.vistas[0].en_bd is None  # BD no consultada: sin veredicto
