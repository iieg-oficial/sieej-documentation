"""Envío del ciclo a mariachi, que guarda la documentación editable.

El datalayer solo reporta lo medido (tablas, vistas, relaciones, DAGs) y lo
que dice el README; mariachi decide qué secciones se siembran, cuáles se
refrescan y cuáles no se tocan porque alguien las editó.
"""

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version

import httpx

from .config import Settings
from .etl_readme import nombres
from .models import EstadoFuente, Fuente, Inventario, PaginaPipeline

RUTA_SYNC = "/api/public/sieej-documentacion/sync"


def _version() -> str:
    try:
        return f"datalayer-{version('sieej-datalayer')}"
    except PackageNotFoundError:
        return "datalayer"


def _readme(pagina: PaginaPipeline) -> dict | None:
    if pagina.documento is None:
        return None
    return pagina.documento.model_dump(
        mode="json", exclude={"nombre", "carpeta", "titulo", "producto", "commit"}
    )


def armar_payload(
    inventario: Inventario,
    paginas: dict[str, PaginaPipeline],
    fuentes: dict[str, Fuente],
    iniciado_en: datetime,
) -> dict:
    pipelines = []
    for nombre, pagina in sorted(paginas.items()):
        p = inventario.pipelines.get(nombre)
        doc = pagina.documento
        carpeta = (p.carpeta_etl if p else None) or nombre
        titulo, producto = (doc.titulo, doc.producto) if doc else nombres(carpeta)
        pipelines.append(
            {
                "clave": nombre,
                "carpeta_etl": p.carpeta_etl if p else None,
                "fuentes_detectadas": p.fuentes_detectadas if p else [],
                "titulo": titulo,
                "producto": producto if producto != titulo else "",
                "clasificacion": pagina.clasificacion.value,
                "readme": _readme(pagina),
                "readme_commit": doc.commit if doc else None,
                "base": pagina.base.model_dump(mode="json") if pagina.base else None,
                "origen_base": pagina.origen_base,
                "corte_respaldo": pagina.corte_respaldo,
                "etapas": [
                    e.model_dump(mode="json") for e in (pagina.etapas or (p.etapas if p else []))
                ],
                "der_svg": pagina.der_svg,
            }
        )
    return {
        "iniciado_en": iniciado_en.astimezone(timezone.utc).replace(tzinfo=None).isoformat(),
        "version": _version(),
        "fuentes": {k: v.model_dump(mode="json") for k, v in fuentes.items()},
        "errores": [
            f"{k}: {v.detalle}" for k, v in fuentes.items() if v.estado is not EstadoFuente.OK
        ],
        "pipelines": pipelines,
    }


def enviar(settings: Settings, payload: dict, transport: httpx.BaseTransport | None = None) -> dict:
    """PUT al endpoint de sincronización; nunca lanza: regresa el resultado o el error."""
    if not settings.mariachi_configurado:
        return {"estado": "sin_configurar"}
    try:
        with httpx.Client(
            base_url=settings.mariachi_url.rstrip("/"),
            timeout=settings.mariachi_timeout,
            transport=transport,
            verify=settings.mariachi_tls_verify,
            headers={"X-API-Key": settings.mariachi_sync_key, "User-Agent": _version()},
        ) as cliente:
            respuesta = cliente.put(RUTA_SYNC, json=payload)
            respuesta.raise_for_status()
            return respuesta.json()
    except Exception as exc:
        return {"estado": "error", "detalle": f"{type(exc).__name__}: {exc}"}
