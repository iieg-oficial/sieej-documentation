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

# En Airflow 3 `logical_date` puede venir nulo; `run_after` siempre viene.
RUNS = {
    "etl_denue": {
        "dag_runs": [
            {"state": "success", "end_date": "2026-08-01T06:10:00+00:00"},
            {"state": "failed", "end_date": "2026-07-01T06:10:00+00:00"},
            {"state": "success", "end_date": "2026-06-01T06:10:00+00:00"},
        ]
    },
    "etl_fiscalia": {"dag_runs": []},
    "etl_sin_fin": {
        "dag_runs": [
            {
                "state": "running",
                "end_date": None,
                "logical_date": None,
                "run_after": "2026-08-20T06:00:00+00:00",
            }
        ]
    },
}

TOKEN = "jwt-de-prueba"


def _settings(**kwargs) -> Settings:
    base = {
        "airflow_base_url": "http://airflow.test",
        "airflow_username": "viewer",
        "airflow_password": "secreto",
    }
    base.update(kwargs)
    return Settings(_env_file=None, **base)


def _transport(peticiones: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if peticiones is not None:
            peticiones.append(request)
        if request.url.path == "/auth/token":
            return httpx.Response(201, json={"access_token": TOKEN})
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"detail": "Not authenticated"})
        if request.url.path == "/api/v2/dags":
            return httpx.Response(200, json=DAGS_PAGINA)
        for dag_id, runs in RUNS.items():
            if request.url.path == f"/api/v2/dags/{dag_id}/dagRuns":
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


def test_intercambia_credenciales_por_un_jwt_y_lo_usa():
    peticiones: list[httpx.Request] = []
    fuente, _ = consultar_airflow(_settings(), transport=_transport(peticiones))
    assert fuente.estado is EstadoFuente.OK
    login = peticiones[0]
    assert login.method == "POST"
    assert login.url.path == "/auth/token"
    # Las demás peticiones son GET autenticados contra la API v2.
    for req in peticiones[1:]:
        assert req.method == "GET"
        assert req.url.path.startswith("/api/v2/")
        assert req.headers["Authorization"] == f"Bearer {TOKEN}"


def test_token_ya_emitido_evita_el_intercambio():
    peticiones: list[httpx.Request] = []
    settings = _settings(airflow_username=None, airflow_password=None, airflow_token=TOKEN)
    fuente, dags = consultar_airflow(settings, transport=_transport(peticiones))
    assert fuente.estado is EstadoFuente.OK
    assert dags
    assert all(req.url.path != "/auth/token" for req in peticiones)


def test_corridas_se_piden_ordenadas_por_run_after():
    peticiones: list[httpx.Request] = []
    consultar_airflow(_settings(), transport=_transport(peticiones))
    corridas = [r for r in peticiones if r.url.path.endswith("/dagRuns")]
    assert corridas
    for req in corridas:
        assert req.url.params["order_by"] == "-run_after"


def test_una_corrida_viva_no_reporta_fecha_sino_su_estado():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/token":
            return httpx.Response(201, json={"access_token": TOKEN})
        if request.url.path == "/api/v2/dags":
            return httpx.Response(
                200,
                json={"dags": [{"dag_id": "etl_sin_fin", "is_paused": False}], "total_entries": 1},
            )
        return httpx.Response(200, json=RUNS["etl_sin_fin"])

    _, dags = consultar_airflow(_settings(), transport=httpx.MockTransport(handler))
    corrida = dags["etl_sin_fin"]
    # Sigue corriendo: no hay `end_date`, y `run_after` es cuándo empezó. Antes
    # se presentaba como fecha de la última corrida, que es una fecha que miente.
    assert corrida.ultima_corrida_estado == "running"
    assert corrida.ultima_corrida_fecha is None


def test_token_sin_access_token_reporta_caida():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"detail": "sin token"})

    fuente, dags = consultar_airflow(_settings(), transport=httpx.MockTransport(handler))
    assert fuente.estado is EstadoFuente.CAIDA
    assert "ErrorAutenticacion" in fuente.detalle
    assert dags == {}


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
        return httpx.Response(401, json={"detail": "Not authenticated"})

    fuente, dags = consultar_airflow(_settings(), transport=httpx.MockTransport(handler))
    assert fuente.estado is EstadoFuente.CAIDA
    assert dags == {}
