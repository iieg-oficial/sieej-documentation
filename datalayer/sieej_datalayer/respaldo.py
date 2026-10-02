"""Respaldo de tablas y vistas para bases que la BD consultada no tiene.

El espejo no replica todas las bases de producción. Para no dejar sin
contenido esas páginas, `respaldo/*.json` guarda tablas (con filas) y vistas
(con columnas) tal como las publicaron los documentos técnicos de pipeline,
generados contra producción. La BD en vivo siempre manda: el respaldo solo se
usa cuando la base no aparece.
"""

import json
import re
from importlib import resources
from pathlib import Path

from .models import BaseDeDatos, Columna, Tabla, Vista


def _leer(nombre: str) -> dict | None:
    archivo = resources.files("sieej_datalayer") / "respaldo" / f"{nombre}.json"
    if not archivo.is_file():
        return None
    return json.loads(archivo.read_text(encoding="utf-8"))


def cargar_respaldo(nombre: str) -> tuple[BaseDeDatos, str | None] | None:
    """(base, fecha de corte) del respaldo de un pipeline, o None si no hay."""
    datos = _leer(nombre)
    if datos is None:
        return None
    base = BaseDeDatos(
        nombre=nombre,
        tablas=[Tabla(**t) for t in datos.get("tablas", [])],
        vistas=[
            Vista(
                nombre=v["nombre"],
                descripcion=v.get("descripcion"),
                columnas=[Columna(**c) for c in v.get("columnas", [])],
                en_docs=True,
            )
            for v in datos.get("vistas", [])
        ],
    )
    return base, datos.get("corte")


_PELIGROSO = re.compile(r"<script\b.*?</script>|\son\w+=\"[^\"]*\"", re.IGNORECASE | re.DOTALL)


def _incrustable(svg: str) -> str | None:
    """SVG sin scripts, con `viewBox` y ancho natural para que el visor lo escale."""
    svg = _PELIGROSO.sub("", svg)
    svg = re.sub(r"^<\?xml[^>]*\?>\s*", "", svg).strip()
    m = re.search(r"<svg([^>]*)>", svg)
    if not m:
        return None
    atributos = m.group(1)
    caja = re.search(r'\sviewBox="0 0 ([\d.]+) ([\d.]+)"', atributos)
    ancho = re.search(r'\swidth="([\d.]+)"', atributos)
    alto = re.search(r'\sheight="([\d.]+)"', atributos)
    medidas = (caja.group(1), caja.group(2)) if caja else (
        (ancho.group(1), alto.group(1)) if ancho and alto else None
    )
    if not medidas:
        return svg
    atributos = re.sub(r'\s(width|height|viewBox)="[^"]*"', "", atributos)
    nuevo = f' viewBox="0 0 {medidas[0]} {medidas[1]}" width="{medidas[0]}"'
    return svg[: m.start()] + f"<svg{nuevo}{atributos}>" + svg[m.end() :]


def svg_der(etl_repo_dir: Path | None, carpeta: str, nombre: str | None = None) -> str | None:
    """El erd.svg del pipeline en ETL-SIEEJ; si no existe, el del respaldo."""
    if etl_repo_dir:
        ruta = Path(etl_repo_dir) / "core" / "pipelines" / carpeta / "assets" / "erd.svg"
        if ruta.is_file():
            return _incrustable(ruta.read_text(encoding="utf-8", errors="replace"))
    datos = _leer(nombre or carpeta)
    if datos and datos.get("der_svg"):
        return _incrustable(datos["der_svg"])
    return None
