"""Orquestación: consulta fuentes, cruza, y escribe data/*.json con degradación.

Política de degradación por archivo: si una fuente viva está caída pero el
JSON previo en disco se generó con esa fuente en `ok`, se conserva el archivo
previo marcado `datos_obsoletos: true` en lugar de sobreescribir datos buenos
con vacíos. La generación nunca lanza: el build del sitio no debe romperse.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .airflow_client import consultar_airflow
from .config import Settings
from .crosscheck import (
    construir_estructura_vistas,
    construir_inventario,
    construir_numeralia,
)
from .db_introspect import consultar_bd
from .models import EstadoFuente
from .static_docs import escanear_html, escanear_views_md

ARCHIVOS = ("inventario.json", "numeralia.json", "vistas.json")


def generar(settings: Settings, transport=None, connect=None) -> dict[str, BaseModel]:
    """Construye los tres modelos del contrato de datos a partir de las fuentes."""
    generado = datetime.now(timezone.utc)
    fuente_html, html_docs = escanear_html(settings.docs_html_dir)
    fuente_views, vistas_docs = escanear_views_md(settings.views_md_dir)
    fuente_airflow, dags = consultar_airflow(settings, transport=transport)
    fuente_bd, bases = consultar_bd(settings, connect=connect)

    fuentes = {
        "airflow": fuente_airflow,
        "bd": fuente_bd,
        "docs_html": fuente_html,
        "views_md": fuente_views,
    }
    inventario = construir_inventario(fuentes, html_docs, vistas_docs, dags, bases, generado)
    numeralia = construir_numeralia(fuentes, inventario, dags, bases, vistas_docs, generado)
    vistas = construir_estructura_vistas(fuentes, bases, vistas_docs, generado)
    return {"inventario.json": inventario, "numeralia.json": numeralia, "vistas.json": vistas}


def _fuente_viva_degradada(nuevo: dict, previo: dict) -> bool:
    """True si alguna fuente viva pasó de `ok` (previo) a no-`ok` (nuevo)."""
    for clave in ("airflow", "bd"):
        estado_nuevo = nuevo.get("fuentes", {}).get(clave, {}).get("estado")
        estado_previo = previo.get("fuentes", {}).get(clave, {}).get("estado")
        if estado_previo == EstadoFuente.OK.value and estado_nuevo != EstadoFuente.OK.value:
            return True
    return False


def escribir(settings: Settings, resultados: dict[str, BaseModel]) -> dict[str, str]:
    """Escribe cada JSON aplicando la política de degradación. Regresa acciones."""
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    acciones: dict[str, str] = {}
    for nombre, modelo in resultados.items():
        destino = data_dir / nombre
        nuevo = modelo.model_dump(mode="json")
        if destino.exists():
            try:
                previo = json.loads(destino.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                previo = None
            if previo and _fuente_viva_degradada(nuevo, previo):
                previo["datos_obsoletos"] = True
                destino.write_text(
                    json.dumps(previo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                acciones[nombre] = "conservado_previo"
                continue
        destino.write_text(json.dumps(nuevo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        acciones[nombre] = "escrito"
    return acciones


def generar_y_escribir(settings: Settings, transport=None, connect=None) -> dict[str, str]:
    """Punto de entrada del build: nunca lanza."""
    try:
        resultados = generar(settings, transport=transport, connect=connect)
        return escribir(settings, resultados)
    except Exception as exc:  # último recurso: el build del sitio sigue en pie
        return {"error": f"{type(exc).__name__}: {exc}"}
