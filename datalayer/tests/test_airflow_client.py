import httpx

from sieej_datalayer.airflow_client import consultar_airflow
from sieej_datalayer.config import Settings
from sieej_datalayer.models import EstadoFuente

DAGS_PAGINA = {
    "dags": [
        {"dag_id": "etl_denue", "is_paused": False},
        {"dag_id": "etl_fiscalia", "is_paused": True},
    ],
    "total_entries": 2,
}

RUNS = {
    "etl_denue": {
        "dag_runs": [
            {"state": "success", "end_date": "2026-08-01T06:10:00+00:00"},
            {"state": "failed", "end_date": "2026-07-01T06:10:00+00:00"},
            {"state": "success", "end_date": "2026-06-01T06:10:00+00:00"},
        ]
    },
    "etl_fiscalia": {"dag_runs": []},
}


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        airflow_base_url="http://airflow.test",
        airflow_username="viewer",
        airflow_password="secreto",
    )


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/dags":
            return httpx.Response(200, json=DAGS_PAGINA)
        for dag_id, runs in RUNS.items():
            if request.url.path == f"/api/v1/dags/{dag_id}/dagRuns":
                return httpx.Response(200, json=runs)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_consulta_exitosa_resume_dags_y_corridas():
    fuente, dags = consultar_airflow(_settings(), transport=_transport())
    assert fuente.estado is EstadoFuente.OK
    assert set(dags) == {"etl_denue", "etl_fiscalia"}
    denue = dags["etl_denue"]
    assert denue.pausado is False
    assert denue.ultima_corrida_estado == "success"
    assert denue.corridas_recientes.exitos == 2
    assert denue.corridas_recientes.fallos == 1
    fiscalia = dags["etl_fiscalia"]
    assert fiscalia.pausado is True
    assert fiscalia.ultima_corrida_fecha is None


def test_sin_configurar_no_intenta_conexion():
    fuente, dags = consultar_airflow(Settings(_env_file=None))
    assert fuente.estado is EstadoFuente.SIN_CONFIGURAR
    assert dags == {}


def test_fuente_caida_no_lanza():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin ruta al host")

    fuente, dags = consultar_airflow(_settings(), transport=httpx.MockTransport(handler))
    assert fuente.estado is EstadoFuente.CAIDA
    assert "ConnectError" in fuente.detalle
    assert dags == {}


def test_error_http_reporta_caida():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"})

    fuente, dags = consultar_airflow(_settings(), transport=httpx.MockTransport(handler))
    assert fuente.estado is EstadoFuente.CAIDA
    assert dags == {}
