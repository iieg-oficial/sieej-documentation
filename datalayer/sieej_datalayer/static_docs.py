"""Lectura de la documentación estática generada fuera de este repositorio.

Los HTML de pipelines y los markdown de vistas son fotografías: aportan
títulos y descripciones, nunca determinan qué existe hoy en producción.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Columna, DocumentacionHtml, EstadoFuente, Fuente, Vista

# Nombre del HTML -> nombre real de la base de datos del pipeline
ALIAS_HTML_A_BD = {"censos_economicos": "censo_economico"}

_RE_TITULO = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_RE_COLUMNA = re.compile(
    r"^\s*(\d+)\s*\|\s*(\S+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(YES|NO)\s*$"
)
_RE_REGISTROS = re.compile(r"\*\*Registros \(aprox\.\)\*\*\s*\|\s*(-?\d+)")
_RE_TIPO = re.compile(r"\*\*Tipo\*\*\s*\|\s*(MATERIALIZED VIEW|VIEW)")


def escanear_html(docs_dir: Path | None) -> tuple[Fuente, dict[str, DocumentacionHtml]]:
    """HTML por nombre de pipeline (ya normalizado con los alias conocidos)."""
    if not docs_dir:
        return Fuente(estado=EstadoFuente.SIN_CONFIGURAR, detalle="Falta DOCS_HTML_DIR"), {}
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        return Fuente(estado=EstadoFuente.CAIDA, detalle=f"No existe {docs_dir}"), {}
    documentos: dict[str, DocumentacionHtml] = {}
    for archivo in sorted(docs_dir.glob("*.html")):
        if archivo.stem == "index":
            continue
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        m = _RE_TITULO.search(texto)
        nombre = ALIAS_HTML_A_BD.get(archivo.stem, archivo.stem)
        documentos[nombre] = DocumentacionHtml(
            archivo=archivo.name,
            titulo=m.group(1).strip() if m else archivo.stem,
        )
    fuente = Fuente(
        estado=EstadoFuente.OK,
        consultado_en=datetime.now(timezone.utc),
        detalle=f"{len(documentos)} documentos HTML",
    )
    return fuente, documentos


def parsear_vista_md(archivo: Path) -> tuple[str, Vista]:
    """(base_de_datos, Vista) a partir de un markdown `bd__esquema__vista.md`."""
    bd, esquema, nombre = archivo.stem.split("__", 2)
    texto = archivo.read_text(encoding="utf-8", errors="replace")

    m_tipo = _RE_TIPO.search(texto)
    m_reg = _RE_REGISTROS.search(texto)
    registros = int(m_reg.group(1)) if m_reg else None
    if registros is not None and registros < 0:
        registros = None

    columnas = [
        Columna(
            posicion=int(m.group(1)),
            nombre=m.group(2),
            tipo=m.group(3).strip(),
            nullable=m.group(5) == "YES",
        )
        for m in (_RE_COLUMNA.match(linea) for linea in texto.splitlines())
        if m
    ]
    vista = Vista(
        esquema=esquema,
        nombre=nombre,
        tipo=m_tipo.group(1) if m_tipo else "VIEW",
        registros=registros,
        columnas=columnas,
        en_docs=True,
        archivo_md=archivo.name,
    )
    return bd, vista


def escanear_views_md(views_dir: Path | None) -> tuple[Fuente, dict[str, list[Vista]]]:
    """Vistas documentadas por base de datos, según `views-md/`."""
    if not views_dir:
        return Fuente(estado=EstadoFuente.SIN_CONFIGURAR, detalle="Falta VIEWS_MD_DIR"), {}
    views_dir = Path(views_dir)
    if not views_dir.is_dir():
        return Fuente(estado=EstadoFuente.CAIDA, detalle=f"No existe {views_dir}"), {}
    por_bd: dict[str, list[Vista]] = {}
    for archivo in sorted(views_dir.glob("*.md")):
        if archivo.name == "README.md" or archivo.stem.count("__") < 2:
            continue
        bd, vista = parsear_vista_md(archivo)
        por_bd.setdefault(bd, []).append(vista)
    fuente = Fuente(
        estado=EstadoFuente.OK,
        consultado_en=datetime.now(timezone.utc),
        detalle=f"{sum(len(v) for v in por_bd.values())} vistas en {len(por_bd)} bases",
    )
    return fuente, por_bd
