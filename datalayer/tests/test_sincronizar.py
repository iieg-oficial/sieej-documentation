import json
from pathlib import Path

import httpx

from sieej_datalayer.config import Settings
from sieej_datalayer.generate import generar_y_escribir

ETL = Path(__file__).parent / "fixtures" / "etl"


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(_env_file=None, etl_repo_dir=ETL, data_dir=tmp_path / "data", **extra)


def test_una_carpeta_sin_readme_tambien_es_un_pipeline(tmp_path):
    generar_y_escribir(_settings(tmp_path))
    inventario = json.loads((tmp_path / "data" / "inventario.json").read_text())
    fosas = inventario["pipelines"]["fosas_clandestinas"]
    assert fosas["documento"] is None
    assert fosas["fuentes_detectadas"] == ["carpeta"]
    assert inventario["pipelines"]["denue"]["fuentes_detectadas"] == ["readme", "carpeta"]
    assert inventario["pipelines"]["censo_economico"]["carpeta_etl"] == "censos_economicos"


def _con_transporte(monkeypatch, responder):
    import sieej_datalayer.generate as generate
    from sieej_datalayer import sincronizar

    original = sincronizar.enviar
    monkeypatch.setattr(
        generate,
        "enviar",
        lambda s, p, transport=None: original(s, p, transport=httpx.MockTransport(responder)),
    )


def test_el_ciclo_se_envia_a_mariachi_con_la_llave(tmp_path, monkeypatch):
    recibido = {}

    def responder(request: httpx.Request) -> httpx.Response:
        recibido["url"] = str(request.url)
        recibido["llave"] = request.headers["X-API-Key"]
        recibido["cuerpo"] = json.loads(request.content)
        return httpx.Response(200, json={"estado": "ok", "nuevos": ["fosas_clandestinas"]})

    _con_transporte(monkeypatch, responder)
    settings = _settings(
        tmp_path, mariachi_url="https://portalito.iieg/", mariachi_sync_key="secreta"
    )
    acciones = generar_y_escribir(settings)
    assert acciones["mariachi"] == "ok"
    assert acciones["mariachi_nuevos"] == "fosas_clandestinas"
    assert recibido["url"] == "https://portalito.iieg/api/public/sieej-documentacion/sync"
    assert recibido["llave"] == "secreta"
    claves = {p["clave"]: p for p in recibido["cuerpo"]["pipelines"]}
    assert claves["fosas_clandestinas"]["titulo"] == "Fosas Clandestinas"
    assert claves["denue"]["readme"]["alcance_vistas"]
    assert claves["denue"]["fuentes_detectadas"] == ["readme", "carpeta"]


def test_si_mariachi_falla_el_ciclo_sigue(tmp_path, monkeypatch):
    _con_transporte(monkeypatch, lambda request: httpx.Response(503))
    settings = _settings(tmp_path, mariachi_url="https://portalito.iieg", mariachi_sync_key="x")
    acciones = generar_y_escribir(settings)
    assert acciones["inventario.json"] == "escrito"
    assert acciones["mariachi"] == "error"
    assert "503" in acciones["mariachi_detalle"]


def test_sin_airflow_se_envian_las_etapas_heredadas_del_inventario(tmp_path, monkeypatch):
    recibido = {}

    def responder(request: httpx.Request) -> httpx.Response:
        recibido["cuerpo"] = json.loads(request.content)
        return httpx.Response(200, json={"estado": "parcial"})

    settings = _settings(tmp_path, mariachi_url="https://portalito.iieg", mariachi_sync_key="x")
    generar_y_escribir(settings)
    destino = tmp_path / "data" / "inventario.json"
    inventario = json.loads(destino.read_text())
    inventario["fuentes"]["airflow"]["estado"] = "ok"
    inventario["pipelines"]["denue"]["etapas"] = [{"dag_id": "etl_denue_update", "etapa": "update"}]
    destino.write_text(json.dumps(inventario), encoding="utf-8")

    _con_transporte(monkeypatch, responder)
    generar_y_escribir(settings)
    claves = {p["clave"]: p for p in recibido["cuerpo"]["pipelines"]}
    assert claves["denue"]["etapas"][0]["dag_id"] == "etl_denue_update"
