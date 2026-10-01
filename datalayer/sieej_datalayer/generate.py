"""Orquestación: consulta fuentes, cruza, y escribe data/*.json con degradación.

Política de degradación por archivo: cada archivo depende de ciertas fuentes.
Si una de ellas pasó de `ok` a caída respecto al JSON previo en disco, se
conserva el archivo previo marcado `datos_obsoletos: true` en lugar de
sobreescribir datos buenos con vacíos.

Airflow es la excepción: su caída no congela el archivo entero, solo hace que
las etapas (estado de los DAG) y las cifras de Airflow se tomen del JSON previo.
Así un Airflow fuera de alcance no detiene la actualización de la documentación
ni de la BD.

La generación nunca lanza: el build del sitio no debe romperse.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .airflow_client import consultar_airflow
from .config import Settings
from .crosscheck import (
    construir_estructura_vistas,
    construir_inventario,
    construir_numeralia,
    construir_paginas,
)
from .db_introspect import consultar_bd
from .etl_readme import leer_documentos
from .models import EstadoFuente

ARCHIVOS = ("inventario.json", "numeralia.json", "vistas.json")
CARPETA_PAGINAS = "pipelines"

# Fuentes cuya caída congela el archivo; Airflow se trata aparte.
FUENTES_CRITICAS = {
    "inventario.json": ("bd", "readme"),
    "numeralia.json": ("bd", "readme"),
    "vistas.json": ("bd",),
    CARPETA_PAGINAS: ("bd", "readme"),
}


def generar(settings: Settings, transport=None, connect=None) -> dict[str, BaseModel]:
    """Construye los modelos del contrato de datos a partir de las fuentes."""
    generado = datetime.now(timezone.utc)
    fuente_readme, documentos = leer_documentos(settings)
    fuente_airflow, dags = consultar_airflow(settings, transport=transport)
    fuente_bd, bases = consultar_bd(settings, connect=connect)

    fuentes = {"airflow": fuente_airflow, "bd": fuente_bd, "readme": fuente_readme}
    inventario = construir_inventario(fuentes, documentos, dags, bases, generado)
    numeralia = construir_numeralia(fuentes, inventario, dags, bases, documentos, generado)
    vistas = construir_estructura_vistas(fuentes, bases, documentos, generado)
    paginas = construir_paginas(fuentes, inventario, vistas, documentos, bases, generado)
    resultados: dict[str, BaseModel] = {
        "inventario.json": inventario,
        "numeralia.json": numeralia,
        "vistas.json": vistas,
    }
    for nombre, pagina in paginas.items():
        resultados[f"{CARPETA_PAGINAS}/{nombre}.json"] = pagina
    return resultados


def _estado(datos: dict, clave: str) -> str | None:
    return datos.get("fuentes", {}).get(clave, {}).get("estado")


def _fuente_degradada(nuevo: dict, previo: dict, claves: tuple[str, ...]) -> bool:
    """True si alguna fuente crítica pasó de `ok` (previo) a no-`ok` (nuevo)."""
    ok = EstadoFuente.OK.value
    return any(_estado(previo, c) == ok and _estado(nuevo, c) != ok for c in claves)


def _heredar_airflow(nuevo: dict, previo: dict) -> bool:
    """Con Airflow caído, toma etapas y cifras del JSON previo. True si heredó algo."""
    ok = EstadoFuente.OK.value
    if _estado(nuevo, "airflow") == ok or _estado(previo, "airflow") != ok:
        return False
    if "pipelines" in nuevo:
        heredo = False
        for nombre, p in nuevo["pipelines"].items():
            anterior = previo.get("pipelines", {}).get(nombre, {})
            if not p.get("etapas") and anterior.get("etapas"):
                p["etapas"] = anterior["etapas"]
                heredo = True
        return heredo
    if "airflow" in nuevo and not nuevo["airflow"] and previo.get("airflow"):
        nuevo["airflow"] = previo["airflow"]
        return True
    if not nuevo.get("etapas") and previo.get("etapas"):
        nuevo["etapas"] = previo["etapas"]
        return True
    return False


def _escribir_atomico(destino: Path, datos: dict) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, destino)


def _leer(destino: Path) -> dict | None:
    if not destino.exists():
        return None
    try:
        return json.loads(destino.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def escribir(settings: Settings, resultados: dict[str, BaseModel]) -> dict[str, str]:
    """Escribe cada JSON aplicando la política de degradación. Regresa acciones."""
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    acciones: dict[str, str] = {}
    for nombre, modelo in resultados.items():
        destino = data_dir / nombre
        clave = nombre.split("/", 1)[0] if "/" in nombre else nombre
        nuevo = modelo.model_dump(mode="json")
        previo = _leer(destino)
        if previo and _fuente_degradada(nuevo, previo, FUENTES_CRITICAS[clave]):
            previo["datos_obsoletos"] = True
            _escribir_atomico(destino, previo)
            acciones[nombre] = "conservado_previo"
            continue
        heredo = bool(previo) and _heredar_airflow(nuevo, previo)
        _escribir_atomico(destino, nuevo)
        acciones[nombre] = "escrito_con_airflow_previo" if heredo else "escrito"
    _retirar_paginas_huerfanas(data_dir, resultados, acciones)
    return acciones


def _retirar_paginas_huerfanas(
    data_dir: Path, resultados: dict[str, BaseModel], acciones: dict[str, str]
) -> None:
    """Quita páginas de pipelines que ya no existen, solo si el inventario es fresco."""
    if acciones.get("inventario.json") == "conservado_previo":
        return
    vigentes = {n for n in resultados if n.startswith(f"{CARPETA_PAGINAS}/")}
    for archivo in (data_dir / CARPETA_PAGINAS).glob("*.json"):
        relativo = f"{CARPETA_PAGINAS}/{archivo.name}"
        if relativo not in vigentes:
            archivo.unlink()
            acciones[relativo] = "retirado"


def generar_y_escribir(settings: Settings, transport=None, connect=None) -> dict[str, str]:
    """Punto de entrada del build: nunca lanza."""
    try:
        resultados = generar(settings, transport=transport, connect=connect)
        return escribir(settings, resultados)
    except Exception as exc:  # último recurso: el build del sitio sigue en pie
        return {"error": f"{type(exc).__name__}: {exc}"}
