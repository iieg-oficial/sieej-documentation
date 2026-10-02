import json
from pathlib import Path

from sieej_datalayer.config import Settings
from sieej_datalayer.generate import escribir, generar, generar_y_escribir

ETL = Path(__file__).parent / "fixtures" / "etl"


def _settings(tmp_path: Path, etl: Path | None = ETL) -> Settings:
    return Settings(_env_file=None, etl_repo_dir=etl, data_dir=tmp_path / "data")


def _leer(settings: Settings, nombre: str) -> dict:
    return json.loads((Path(settings.data_dir) / nombre).read_text())


def test_sin_fuentes_vivas_se_escriben_los_json_y_una_pagina_por_pipeline(tmp_path):
    settings = _settings(tmp_path)
    acciones = generar_y_escribir(settings)
    assert acciones["inventario.json"] == "escrito"
    assert acciones["pipelines/denue.json"] == "escrito"
    inventario = _leer(settings, "inventario.json")
    assert inventario["fuentes"]["airflow"]["estado"] == "sin_configurar"
    assert inventario["fuentes"]["readme"]["estado"] == "ok"
    esperados = {"denue", "conapo", "censo_economico", "fosas_clandestinas"}
    assert set(inventario["pipelines"]) == esperados
    assert inventario["pipelines"]["denue"]["documento"]["titulo"] == "DENUE"

    pagina = _leer(settings, "pipelines/denue.json")
    assert pagina["documento"]["alcance_vistas"]
    assert pagina["origen_base"] == "respaldo"

    numeralia = _leer(settings, "numeralia.json")
    assert numeralia["airflow"] == {}
    assert numeralia["documentacion"]["pipelines_documentados"] == 3


def test_un_clon_vacio_no_vacia_el_inventario(tmp_path):
    generar_y_escribir(_settings(tmp_path))
    vacio = tmp_path / "etl-vacio"
    vacio.mkdir()
    acciones = generar_y_escribir(_settings(tmp_path, vacio))
    assert acciones["inventario.json"] == "conservado_previo"
    assert "pipelines/denue.json" not in acciones
    conservado = _leer(_settings(tmp_path), "inventario.json")
    assert conservado["datos_obsoletos"] is True
    assert "denue" in conservado["pipelines"]
    assert (tmp_path / "data/pipelines/conapo.json").exists()


def test_la_bd_caida_conserva_vistas_pero_no_detiene_lo_demas(tmp_path):
    settings = _settings(tmp_path)
    resultados = generar(settings)
    previo = resultados["vistas.json"].model_dump(mode="json")
    previo["fuentes"]["bd"]["estado"] = "ok"
    previo["bases"] = [{"nombre": "denue", "es_infraestructura": False, "vistas": []}]
    destino = Path(settings.data_dir) / "vistas.json"
    destino.parent.mkdir(parents=True)
    destino.write_text(json.dumps(previo), encoding="utf-8")

    acciones = escribir(settings, resultados)
    assert acciones["vistas.json"] == "conservado_previo"
    assert _leer(settings, "vistas.json")["datos_obsoletos"] is True
    assert acciones["inventario.json"] == "escrito"


def test_airflow_caido_hereda_las_etapas_previas(tmp_path):
    settings = _settings(tmp_path)
    resultados = generar(settings)
    previo = resultados["inventario.json"].model_dump(mode="json")
    previo["fuentes"]["airflow"]["estado"] = "ok"
    etapa = {"dag_id": "etl_denue_update", "etapa": "update", "pausado": False}
    previo["pipelines"]["denue"]["etapas"] = [etapa]
    destino = Path(settings.data_dir) / "inventario.json"
    destino.parent.mkdir(parents=True)
    destino.write_text(json.dumps(previo), encoding="utf-8")

    acciones = escribir(settings, resultados)
    assert acciones["inventario.json"] == "escrito_con_airflow_previo"
    inventario = _leer(settings, "inventario.json")
    assert inventario["pipelines"]["denue"]["etapas"][0]["dag_id"] == "etl_denue_update"
    assert inventario["datos_obsoletos"] is False


def test_las_paginas_de_pipelines_retirados_se_borran(tmp_path):
    settings = _settings(tmp_path)
    huerfana = Path(settings.data_dir) / "pipelines" / "retirado.json"
    huerfana.parent.mkdir(parents=True)
    huerfana.write_text("{}", encoding="utf-8")
    acciones = generar_y_escribir(settings)
    assert acciones["pipelines/retirado.json"] == "retirado"
    assert not huerfana.exists()


def test_json_previo_corrupto_no_rompe(tmp_path):
    settings = _settings(tmp_path)
    destino = Path(settings.data_dir) / "numeralia.json"
    destino.parent.mkdir(parents=True)
    destino.write_text("{corrupto", encoding="utf-8")
    acciones = generar_y_escribir(settings)
    assert acciones["numeralia.json"] == "escrito"
    json.loads(destino.read_text())


def test_airflow_caido_conserva_las_cifras_de_la_numeralia(tmp_path):
    settings = _settings(tmp_path)
    resultados = generar(settings)
    previo = resultados["numeralia.json"].model_dump(mode="json")
    previo["fuentes"]["airflow"]["estado"] = "ok"
    previo["airflow"] = {"dags_total": 56}
    destino = Path(settings.data_dir) / "numeralia.json"
    destino.parent.mkdir(parents=True)
    destino.write_text(json.dumps(previo), encoding="utf-8")

    acciones = escribir(settings, resultados)
    assert acciones["numeralia.json"] == "escrito_con_airflow_previo"
    assert _leer(settings, "numeralia.json")["airflow"] == {"dags_total": 56}


def test_las_etapas_heredadas_sobreviven_a_varias_corridas_sin_airflow(tmp_path):
    settings = _settings(tmp_path)
    resultados = generar(settings)
    previo = resultados["inventario.json"].model_dump(mode="json")
    previo["fuentes"]["airflow"]["estado"] = "ok"
    previo["pipelines"]["denue"]["etapas"] = [{"dag_id": "etl_denue_update"}]
    destino = Path(settings.data_dir) / "inventario.json"
    destino.parent.mkdir(parents=True)
    destino.write_text(json.dumps(previo), encoding="utf-8")

    generar_y_escribir(settings)
    generar_y_escribir(settings)
    inventario = _leer(settings, "inventario.json")
    assert inventario["fuentes"]["airflow"]["estado"] == "sin_configurar"
    assert inventario["pipelines"]["denue"]["etapas"][0]["dag_id"] == "etl_denue_update"
