"""Cliente de solo lectura de la API REST de Airflow (Airflow 2.x, `/api/v1`).

Solo métodos GET: nunca dispara DAGs ni modifica estado en el servidor.
"""

from datetime import datetime, timezone

import httpx

from .config import Settings
from .models import CorridasRecientes, Dag, EstadoFuente, Fuente

_PAGE_SIZE = 100


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
            auth=(settings.airflow_username, settings.airflow_password),
            timeout=settings.airflow_timeout,
            transport=transport,
        )
        self._recent_runs = settings.airflow_recent_runs

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
            resp = self._client.get("/api/v1/dags", params={"limit": _PAGE_SIZE, "offset": offset})
            resp.raise_for_status()
            payload = resp.json()
            dags.extend(payload.get("dags", []))
            offset += _PAGE_SIZE
            if offset >= payload.get("total_entries", 0):
                return dags

    def get_dag_runs(self, dag_id: str) -> list[dict]:
        """Corridas recientes de un DAG, de la más nueva a la más vieja."""
        resp = self._client.get(
            f"/api/v1/dags/{dag_id}/dagRuns",
            params={"limit": self._recent_runs, "order_by": "-execution_date"},
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
            ultima_corrida_fecha=_parse_fecha(
                (ultima or {}).get("end_date") or (ultima or {}).get("execution_date")
            ),
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
                detalle="Faltan AIRFLOW_BASE_URL/AIRFLOW_USERNAME/AIRFLOW_PASSWORD",
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
