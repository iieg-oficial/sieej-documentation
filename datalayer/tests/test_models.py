from datetime import datetime

from sieej_datalayer.models import (
    ClasificacionPipeline,
    EstadoFuente,
    Fuente,
    Inventario,
    Pipeline,
    Vista,
)


def test_pipeline_sin_verificar_por_defecto():
    p = Pipeline(nombre="denue")
    assert p.clasificacion is ClasificacionPipeline.SIN_VERIFICAR
    assert p.dag is None
    assert p.bd_existe is None


def test_inventario_serializa_a_json():
    inv = Inventario(
        generado=datetime(2026, 8, 12),
        fuentes={"airflow": Fuente(estado=EstadoFuente.SIN_CONFIGURAR)},
        pipelines={"denue": Pipeline(nombre="denue")},
    )
    data = inv.model_dump(mode="json")
    assert data["fuentes"]["airflow"]["estado"] == "sin_configurar"
    assert data["pipelines"]["denue"]["clasificacion"] == "sin_verificar"


def test_vista_banderas_cross_check():
    v = Vista(nombre="v_establecimientos", en_bd=True, en_docs=False, solo_en_bd=True)
    assert v.solo_en_bd and not v.solo_en_docs
