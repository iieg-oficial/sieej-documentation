import json
from pathlib import Path

from sieej_datalayer.config import Settings
from sieej_datalayer.generate import escribir, generar, generar_y_escribir

FIXTURES = Path(__file__).parent / "fixtures"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        docs_html_dir=FIXTURES / "html-documents",
        views_md_dir=FIXTURES / "views-md",
        data_dir=tmp_path,
    )


def test_generar_sin_fuentes_vivas_produce_los_tres_json(tmp_path):
    settings = _settings(tmp_path)
    acciones = generar_y_escribir(settings)
    assert acciones == {
        "inventario.json": "escrito",
        "numeralia.json": "escrito",
        "vistas.json": "escrito",
    }
    inventario = json.loads((tmp_path / "inventario.json").read_text())
    assert inventario["fuentes"]["airflow"]["estado"] == "sin_configurar"
    assert inventario["fuentes"]["docs_html"]["estado"] == "ok"
    assert set(inventario["pipelines"]) >= {"denue", "conapo", "censo_economico", "fiscalia"}
    assert inventario["datos_obsoletos"] is False

    numeralia = json.loads((tmp_path / "numeralia.json").read_text())
    assert numeralia["airflow"] == {}  # fuente no consultada: sin cifras inventadas
    assert numeralia["documentacion"]["html_pipelines"] == 3

    vistas = json.loads((tmp_path / "vistas.json").read_text())
    assert {b["nombre"] for b in vistas["bases"]} == {"denue", "fiscalia"}


def test_degradacion_conserva_json_previo_bueno(tmp_path):
    settings = _settings(tmp_path)
    resultados = generar(settings)

    # Simula una corrida previa donde la BD sí respondió
    previo = resultados["vistas.json"].model_dump(mode="json")
    previo["fuentes"]["bd"]["estado"] = "ok"
    previo["bases"] = [{"nombre": "denue", "es_infraestructura": False, "vistas": []}]
    (tmp_path / "vistas.json").write_text(json.dumps(previo), encoding="utf-8")

    acciones = escribir(settings, resultados)
    assert acciones["vistas.json"] == "conservado_previo"
    conservado = json.loads((tmp_path / "vistas.json").read_text())
    assert conservado["datos_obsoletos"] is True
    assert conservado["bases"][0]["nombre"] == "denue"
    # Los archivos sin datos vivos previos sí se reescriben
    assert acciones["inventario.json"] == "escrito"


def test_json_previo_corrupto_no_rompe(tmp_path):
    settings = _settings(tmp_path)
    (tmp_path / "numeralia.json").write_text("{corrupto", encoding="utf-8")
    acciones = generar_y_escribir(settings)
    assert acciones["numeralia.json"] == "escrito"
    json.loads((tmp_path / "numeralia.json").read_text())
