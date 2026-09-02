"""Cliente de solo lectura de la API REST de Airflow (Airflow 3.x, `/api/v2`).

Solo métodos GET sobre la API: nunca dispara DAGs ni modifica estado en el
servidor. El único POST es el intercambio de credenciales por un JWT en
`/auth/token`, que es como autentica Airflow 3 (la API ignora HTTP Basic).
"""

from datetime import datetime, timezone

import httpx

from .config import Settings
from .models import CorridasRecientes, Dag, EstadoFuente, Fuente

_PAGE_SIZE = 100


class ErrorAutenticacion(RuntimeError):
    """El servidor no entregó un token utilizable."""


def _parse_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


class AirflowClient:
    """Envoltura mínima sobre httpx para los endpoints que usa la landing."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=settings.airflow_base_url.rstrip("/"),
            timeout=settings.airflow_timeout,
            transport=transport,
        )
        self._recent_runs = settings.airflow_recent_runs
        self._client.headers["Authorization"] = f"Bearer {self._token(settings)}"

    def _token(self, settings: Settings) -> str:
        """El JWT de la configuración, o uno recién pedido a `/auth/token`."""
        if settings.airflow_token:
            return settings.airflow_token
        resp = self._client.post(
            settings.airflow_token_path,
            json={"username": settings.airflow_username, "password": settings.airflow_password},
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise ErrorAutenticacion(f"{settings.airflow_token_path} respondió sin access_token")
        return token

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AirflowClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get_dags(self) -> list[dict]:
        """Todos los DAGs, paginando hasta agotar `total_entries`."""
        dags: list[dict] = []
        offset = 0
        while True:
            resp = self._client.get("/api/v2/dags", params={"limit": _PAGE_SIZE, "offset": offset})
            resp.raise_for_status()
            payload = resp.json()
            dags.extend(payload.get("dags", []))
            offset += _PAGE_SIZE
            if offset >= payload.get("total_entries", 0):
                return dags

    def get_dag_runs(self, dag_id: str) -> list[dict]:
        """Corridas recientes de un DAG, de la más nueva a la más vieja.

        Se ordena por `run_after`: Airflow 3 retiró `execution_date` de los
        atributos ordenables, y `logical_date` puede venir nulo (corridas
        manuales o disparadas por assets).
        """
        resp = self._client.get(
            f"/api/v2/dags/{dag_id}/dagRuns",
            params={"limit": self._recent_runs, "order_by": "-run_after"},
        )
        resp.raise_for_status()
        return resp.json().get("dag_runs", [])

    def resumen_dag(self, dag: dict) -> Dag:
        """Construye el resumen de un DAG con su última corrida y conteos."""
        runs = self.get_dag_runs(dag["dag_id"])
        corridas = CorridasRecientes(
            total=len(runs),
            exitos=sum(1 for r in runs if r.get("state") == "success"),
            fallos=sum(1 for r in runs if r.get("state") == "failed"),
        )
        ultima = runs[0] if runs else None
        return Dag(
            dag_id=dag["dag_id"],
            pausado=dag.get("is_paused"),
            # Solo la fecha de finalización: mientras la corrida sigue viva no hay
            # `end_date`, y `run_after` es cuándo empezó, no cuándo terminó.
            # Presentarla como «última corrida» sería una fecha que miente; en su
            # lugar el campo queda vacío y el estado dice que está en ejecución.
            ultima_corrida_fecha=_parse_fecha((ultima or {}).get("end_date")),
            ultima_corrida_estado=(ultima or {}).get("state"),
            corridas_recientes=corridas,
        )


def consultar_airflow(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> tuple[Fuente, dict[str, Dag]]:
    """Consulta Airflow y regresa (estado de la fuente, DAGs por id).

    Nunca lanza: si la fuente está caída o sin configurar, lo reporta en `Fuente`
    y regresa un diccionario vacío para que el generador degrade con gracia.
    """
    if not settings.airflow_configurado:
        return (
            Fuente(
                estado=EstadoFuente.SIN_CONFIGURAR,
                detalle=(
                    "Faltan AIRFLOW_BASE_URL y credenciales "
                    "(AIRFLOW_TOKEN, o AIRFLOW_USERNAME/AIRFLOW_PASSWORD)"
                ),
            ),
            {},
        )
    try:
        with AirflowClient(settings, transport=transport) as client:
            dags = {d["dag_id"]: client.resumen_dag(d) for d in client.get_dags()}
        fuente = Fuente(
            estado=EstadoFuente.OK,
            consultado_en=datetime.now(timezone.utc),
            detalle=f"{len(dags)} DAGs",
        )
        return fuente, dags
    except Exception as exc:  # red caída, credenciales inválidas, API distinta…
        return Fuente(estado=EstadoFuente.CAIDA, detalle=f"{type(exc).__name__}: {exc}"), {}
