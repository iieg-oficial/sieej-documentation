#!/usr/bin/env python3
"""Genera la documentación HTML de un pipeline, homologada a las existentes.

Toma como fuentes las mismas tres que declara el pie de los documentos ya
publicados: el README del pipeline en ETL-SIEEJ, el diagrama entidad-relación
del propio repositorio, y la base de datos de producción (conteos exactos,
comentarios de tabla y estructura de columnas de cada vista). La programación
de los DAG se lee de la API de Airflow.

El estilo no se reescribe: se hereda de `scripts/plantilla/`, extraída una vez
de un documento publicado y versionada aquí, de modo que los documentos no
puedan divergir del formato y el generador no dependa de su propia salida.

Las rutas se leen del entorno (ver `.env.example`), no del disco de nadie:

    ETL_REPO_DIR   clon de ETL-SIEEJ con los README y los erd.svg
    ETL_REPO_REF   rama de referencia que se lee de ese clon (default origin/main)
    DOCS_HTML_DIR  directorio de los documentos: fuente del índice y destino

Qué pipelines faltan no se escribe a mano: sale de `data/inventario.json`, el
cruce del datalayer, para que un ETL nuevo no quede invisible al generador.

Uso:
    .venv/bin/python scripts/generar_doc_pipeline.py emec ems           # algunos
    .venv/bin/python scripts/generar_doc_pipeline.py --todos-faltantes  # inventario
    .venv/bin/python scripts/generar_doc_pipeline.py --solo-navegacion  # nav
"""

from __future__ import annotations

import argparse
import html
import json
import locale
import re
import subprocess
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

# La plantilla vive en este repositorio, no en el directorio de salida: así el
# generador no depende de un documento que él mismo pudo haber escrito.
PLANTILLA = Path(__file__).resolve().parent / "plantilla"
RAIZ = Path(__file__).resolve().parent.parent
INVENTARIO = RAIZ / "data" / "inventario.json"

# Nombre corto (barra lateral y título) y nombre del producto (subtítulo del
# hero) de los pipelines que todavía no tienen documento. El README no los
# expone en un campo propio, así que se curan aquí mientras no exista ese campo
# aguas arriba. Los pipelines ya documentados NO necesitan entrada: su nombre se
# lee del propio documento (ver `etiquetas_existentes`).
NOMBRES: dict[str, tuple[str, str]] = {
    "defunciones": ("Defunciones", "Registro de defunciones generales — DGIS"),
    # Los mismos hechos que `defunciones`, con otra fuente y otro esquema: el
    # README de ETL-SIEEJ advierte de la confusión, así que el nombre la deshace.
    "defunciones_inegi": ("Defunciones (INEGI)", "Estadísticas de Defunciones Registradas — EDR"),
    "edafologia": ("Edafología", "Edafología histórica 1:250 000, Serie III — INEGI"),
    "emec": ("EMEC", "Encuesta Mensual sobre Empresas Comerciales"),
    "emim": ("EMIM", "Encuesta Mensual de la Industria Manufacturera"),
    "ems": ("EMS", "Encuesta Mensual de Servicios"),
    "enec": ("ENEC", "Encuesta Nacional de Empresas Constructoras"),
    "enoe": ("ENOE", "Encuesta Nacional de Ocupación y Empleo"),
    "enoe_microdatos": ("ENOE Microdatos", "ENOE — microdatos completos (SDEM + COE1 + COE2)"),
    "intensidad_migratoria": ("Intensidad Migratoria", "Índice de Intensidad Migratoria México-EUA"),
    "indice_shf_vivienda": ("Índice SHF Vivienda", "Índice SHF de Precios de la Vivienda en México"),
    "rastros": ("Rastros (ESGRM)", "Sacrificio de Ganado en Rastros Municipales"),
    "scian": ("SCIAN", "Sistema de Clasificación Industrial de América del Norte 2023"),
}


# ── Configuración: rutas por entorno, nunca incrustadas ────────────────────


@lru_cache(maxsize=1)
def ajustes():
    """`Settings` del datalayer, que es donde vive la configuración del proyecto."""
    sys.path.insert(0, str(RAIZ / "datalayer"))
    from sieej_datalayer.config import Settings

    return Settings()


def _ruta(nombre: str, variable: str) -> Path:
    valor = getattr(ajustes(), nombre)
    if valor is None:
        raise SystemExit(
            f"falta {variable}: defínela en .env (ver .env.example) o en el entorno"
        )
    # Relativa a la raíz del repositorio, no al directorio de trabajo: en el
    # servidor esto corre desde un cron, no desde donde vive el .env.
    ruta = Path(valor).expanduser()
    if not ruta.is_absolute():
        ruta = (RAIZ / ruta).resolve()
    if not ruta.is_dir():
        raise SystemExit(f"{variable}={ruta} no es un directorio existente")
    return ruta


def repo_etl() -> Path:
    """Clon de ETL-SIEEJ del que se leen README y diagramas."""
    return _ruta("etl_repo_dir", "ETL_REPO_DIR")


def docs_dir() -> Path:
    """Directorio de los documentos HTML: fuente del índice y destino de la salida."""
    return _ruta("docs_html_dir", "DOCS_HTML_DIR")


def ref_git() -> str:
    return ajustes().etl_repo_ref


def nombres(pipeline: str, indice: list[tuple[str, str]] | None = None) -> tuple[str, str]:
    """Nombre corto y nombre de producto, con degradación explícita.

    Un pipeline nuevo que nadie curó no debe reventar la generación: cae a un
    nombre derivado de la clave y lo avisa, para que se note y se corrija.
    """
    if pipeline in NOMBRES:
        return NOMBRES[pipeline]
    derivado = pipeline.replace("_", " ").title()
    print(
        f"  aviso: '{pipeline}' no tiene nombre curado en NOMBRES; se usa "
        f"'{derivado}'. Agrégalo al diccionario si el nombre importa.",
        file=sys.stderr,
    )
    return derivado, derivado


# ── Qué pipelines faltan: se calcula, no se escribe a mano ────────────────


def pipelines_faltantes() -> list[str]:
    """Pipelines del inventario que todavía no tienen documento HTML.

    El inventario lo produce el cruce del datalayer (`data/inventario.json`).
    Se calcula en vez de mantenerse a mano para que un ETL nuevo no quede
    invisible al generador.
    """
    if not INVENTARIO.exists():
        raise SystemExit(
            f"no existe {INVENTARIO}: corre el cruce del datalayer antes de usar "
            "--todos-faltantes, o nombra los pipelines explícitamente"
        )
    inventario = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    documentados = {p.stem for p in docs_dir().glob("*.html")}
    return sorted(
        nombre
        for nombre, datos in inventario.get("pipelines", {}).items()
        if nombre not in documentados and not datos.get("documentacion_html")
    )


# ── Lectura de las fuentes ─────────────────────────────────────────────────


def desde_git(ruta: str) -> str | None:
    """Contenido de un archivo en la rama de referencia de ETL-SIEEJ."""
    r = subprocess.run(
        ["git", "show", f"{ref_git()}:{ruta}"],
        cwd=repo_etl(),
        capture_output=True,
        text=True,
    )
    return r.stdout if r.returncode == 0 else None


@lru_cache(maxsize=1)
def commit_referencia() -> str:
    """SHA corto de la rama de referencia, para que la salida sea rastreable.

    El script nunca hace `fetch`: lee lo que el clon local tenga. Registrar el
    commit deja constancia de qué versión del README se documentó.
    """
    r = subprocess.run(
        ["git", "rev-parse", "--short", ref_git()],
        cwd=repo_etl(),
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else "desconocido"


def secciones_readme(md: str) -> dict[str, str]:
    """Parte el README en sus secciones de nivel `##`."""
    partes: dict[str, str] = {}
    actual, buffer = None, []
    for linea in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", linea)
        if m and not linea.startswith("###"):
            if actual:
                partes[actual] = "\n".join(buffer).strip()
            actual, buffer = m.group(1), []
        elif actual is not None:
            buffer.append(linea)
    if actual:
        partes[actual] = "\n".join(buffer).strip()
    return partes


def subsecciones(texto: str) -> dict[str, str]:
    """Igual que `secciones_readme` pero para los `###` de una sección."""
    partes: dict[str, str] = {}
    actual, buffer = None, []
    for linea in texto.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", linea)
        if m:
            if actual:
                partes[actual] = "\n".join(buffer).strip()
            actual, buffer = m.group(1), []
        elif actual is not None:
            buffer.append(linea)
    if actual:
        partes[actual] = "\n".join(buffer).strip()
    return partes


def filas_tabla(md: str) -> list[list[str]]:
    """Filas de la primera tabla markdown del texto, sin encabezado ni guiones."""
    filas = []
    for linea in md.splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            if filas:
                break
            continue
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in celdas):
            continue
        filas.append(celdas)
    return filas[1:] if filas else []


def enriquecer(texto: str) -> str:
    """Markdown en línea (negritas, código, enlaces) a HTML, ya escapado."""
    t = html.escape(texto)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"(?<![\">])(https?://[^\s<)]+)", r'<a href="\1">\1</a>', t)
    return t


def parrafos(texto: str, limite: int | None = None) -> list[str]:
    """Párrafos del texto, ignorando citas, tablas, listas y bloques de código."""
    fuera: list[str] = []
    en_codigo = False
    for bloque in re.split(r"\n\s*\n", texto):
        bloque = bloque.strip()
        if bloque.startswith("```"):
            en_codigo = not en_codigo or bloque.count("```") % 2 == 0
            continue
        if not bloque or en_codigo or bloque.startswith(("|", "-", "*", ">", "!")):
            continue
        fuera.append(" ".join(bloque.split()))
        if limite and len(fuera) >= limite:
            break
    return fuera


# ── Fuentes vivas: base de datos y Airflow ─────────────────────────────────

# Lo que instala una extensión —PostGIS publica `spatial_ref_sys`,
# `geometry_columns` y `geography_columns` en `public`— no es del pipeline. Se
# excluye por pertenencia a la extensión y no por lista de nombres, para que
# cualquier extensión futura quede fuera sin tocar el generador.
SIN_EXTENSIONES = """
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
"""

SQL_TABLAS = f"""
SELECT c.relname, obj_description(c.oid)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
   AND c.relname <> 'flyway_schema_history'
   {SIN_EXTENSIONES}
 ORDER BY c.relname
"""

SQL_VISTAS = f"""
SELECT c.relname, c.relkind, obj_description(c.oid)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm')
   {SIN_EXTENSIONES}
 ORDER BY c.relname
"""

SQL_COLUMNAS = """
SELECT a.attnum, a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid
 WHERE n.nspname = 'public' AND c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY a.attnum
"""


def _contar(cur, tabla: str, timeout_ms: int = 20000) -> int | None:
    """COUNT(*) exacto con timeout; si excede, cae al estimado del catálogo."""
    try:
        cur.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
        cur.execute(f'SELECT count(*) FROM public."{tabla}"')
        return cur.fetchone()[0]
    except Exception:
        cur.execute("ROLLBACK")
        cur.execute(
            "SELECT GREATEST(c.reltuples,0)::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=%s",
            (tabla,),
        )
        f = cur.fetchone()
        return f[0] if f else None


def datos_bd(base: str) -> dict:
    """Tablas, vistas y columnas reales de la base de producción del pipeline."""
    import psycopg

    s = ajustes()
    salida: dict = {"tablas": [], "vistas": [], "consultado": date.today()}
    with psycopg.connect(**s.pg_conninfo(base)) as conn, conn.cursor() as cur:
        cur.execute(SQL_TABLAS)
        tablas = cur.fetchall()
        for nombre, comentario in tablas:
            salida["tablas"].append(
                {"nombre": nombre, "comentario": comentario, "filas": _contar(cur, nombre)}
            )
        cur.execute(SQL_VISTAS)
        for nombre, kind, comentario in cur.fetchall():
            cur.execute(SQL_COLUMNAS, (nombre,))
            columnas = cur.fetchall()
            salida["vistas"].append(
                {
                    "nombre": nombre,
                    "materializada": kind == "m",
                    "comentario": comentario,
                    "columnas": columnas,
                }
            )
    return salida


def datos_airflow(pipeline: str) -> list[dict]:
    """DAGs del pipeline con su descripción y su programación, desde Airflow."""
    ajustes()  # deja el datalayer en sys.path
    from sieej_datalayer.airflow_client import AirflowClient
    from sieej_datalayer.crosscheck import partir_dag_id

    s = ajustes()
    if not s.airflow_configurado:
        return []
    with AirflowClient(s) as c:
        dags = c.get_dags()
    propios = [d for d in dags if partir_dag_id(d["dag_id"])[0] == pipeline]
    return sorted(
        (
            {
                "dag_id": d["dag_id"],
                "descripcion": d.get("description"),
                "programacion": d.get("timetable_summary"),
                "detalle_programacion": d.get("timetable_description"),
                "pausado": d.get("is_paused"),
            }
            for d in propios
        ),
        key=lambda d: d["dag_id"],
    )


# ── Plantilla: se hereda del documento de referencia, no se reescribe ──────


def plantilla() -> tuple[str, str]:
    """Devuelve (cabecera hasta <body>, script final) de la plantilla del repo.

    Se extrajo una vez de un documento publicado y se versiona aquí: el formato
    sigue siendo uno solo para todos, pero su fuente de verdad es el repositorio
    y no un archivo del directorio de salida.
    """
    return (
        (PLANTILLA / "cabecera.html").read_text(encoding="utf-8"),
        (PLANTILLA / "script.html").read_text(encoding="utf-8"),
    )


def svg_incrustable(pipeline: str) -> str | None:
    """El erd.svg del repo, adaptado como los documentos ya publicados.

    El control de zoom del documento lee `viewBox`, que el archivo original no
    trae: se deriva de su `width`/`height`, y estos pasan a 100% para que el
    diagrama escale dentro de la tarjeta.
    """
    svg = desde_git(f"core/pipelines/{pipeline}/assets/erd.svg")
    if not svg:
        return None
    svg = re.sub(r"^<\?xml[^>]*\?>\s*", "", svg).strip()
    m = re.search(r'<svg([^>]*)>', svg)
    if not m:
        return None
    attrs = m.group(1)
    w = re.search(r'width="([\d.]+)"', attrs)
    h = re.search(r'height="([\d.]+)"', attrs)
    if not (w and h):
        return svg
    nuevos = re.sub(r'\s(width|height)="[\d.]+"', "", attrs)
    nuevos = f' width="100%" height="100%" viewBox="0 0 {w.group(1)} {h.group(1)}"{nuevos}'
    return svg[: m.start()] + f"<svg{nuevos}>" + svg[m.end() :]


def tarjeta(icono: str, titulo: str, cuerpo: str) -> str:
    return (
        f'\n  <section class="card">\n'
        f'    <h2><span class="ico">{icono}</span>{titulo}</h2>\n'
        f"{cuerpo}\n  </section>\n"
    )


def tabla_html(encabezados: list[str], filas: list[list[str]], clases: list[str] | None = None) -> str:
    clases = clases or [""] * len(encabezados)
    th = "".join(
        f'<th{" style=\'text-align:right\'" if c == "num" else ""}>{h}</th>'
        for h, c in zip(encabezados, clases)
    )
    cuerpo = []
    for fila in filas:
        tds = "".join(
            f"<td{f' class=\'{c}\'' if c else ''}>{v}</td>" for v, c in zip(fila, clases)
        )
        cuerpo.append(f"<tr>{tds}</tr>")
    return (
        f"    <table><thead><tr>{th}</tr></thead>\n"
        f"    <tbody>{chr(10).join(cuerpo)}</tbody></table>"
    )


# ── Secciones del documento ───────────────────────────────────────────────


def seccion_descripcion(sec: dict) -> str:
    ps = parrafos(sec.get("Descripción general", ""))
    if not ps:
        return ""
    cuerpo = f'    <p class="lead">{enriquecer(ps[0])}</p>'
    for extra in ps[1:3]:
        cuerpo += f"\n    <p>{enriquecer(extra)}</p>"
    # Las advertencias del README (líneas de cita) son parte del contenido.
    avisos = [
        " ".join(b.lstrip("> ").split())
        for b in re.split(r"\n\s*\n", sec.get("Descripción general", ""))
        if b.strip().startswith(">")
    ]
    for aviso in avisos:
        cuerpo += f'\n    <p class="note">{enriquecer(aviso)}</p>'
    return tarjeta("📋", "Descripción", cuerpo)


def seccion_fuente(pipeline: str, sec: dict) -> str:
    items: list[tuple[str, str]] = []
    _corto, producto = nombres(pipeline)
    items.append(("Dataset (producto)", html.escape(producto)))
    for car, valor in filas_tabla(sec.get("Características de los datos", "")):
        items.append((html.escape(car), enriquecer(valor)))
    general = parrafos(sec.get("Fuente general", ""), 1)
    if general:
        items.append(("Fuente general", enriquecer(general[0])))
    especifica = re.search(r"```[a-z]*\n(.*?)```", sec.get("Fuente específica", ""), re.S)
    if especifica:
        lineas = [l for l in especifica.group(1).strip().splitlines() if "=" in l]
        for linea in lineas[:2]:
            var, _, url = linea.partition("=")
            items.append(
                (
                    "URL de descarga",
                    f"{enriquecer(url.strip())}<div class='muted'>{html.escape(var.strip())}</div>",
                )
            )
    items.append(("Base de datos", f"<code>{html.escape(pipeline)}</code>"))
    dl = "\n".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in items)
    return tarjeta("🗄️", "Fuente de datos", f"    <dl class='src-grid'>\n{dl}\n</dl>")


def _descripcion_tabla(nombre: str, comentario: str | None, sec: dict) -> str:
    if comentario:
        return html.escape(comentario)
    # Sin COMMENT en la base, cae al diccionario del README.
    dicc = subsecciones(sec.get("Diccionario de variables", ""))
    for titulo, cuerpo in dicc.items():
        if titulo.strip("`") == nombre:
            ps = parrafos(cuerpo, 1)
            if ps:
                return enriquecer(ps[0])
    for fila in filas_tabla(dicc.get("Catálogos", "")):
        if len(fila) >= 2 and fila[0].strip("` ") == nombre:
            return enriquecer(fila[1])
    return "<span class='muted'>Sin descripción registrada.</span>"


def seccion_tablas(sec: dict, bd: dict) -> str:
    primarias = [t for t in bd["tablas"] if not t["nombre"].startswith("cat_")]
    secundarias = [t for t in bd["tablas"] if t["nombre"].startswith("cat_")]
    partes = []
    for titulo, etiqueta, clase, grupo in (
        ("Tablas primarias (hechos / datos principales)", "PRIMARIAS", "pri", primarias),
        ("Tablas secundarias (catálogos / dimensiones)", "SECUNDARIAS", "sec", secundarias),
    ):
        if not grupo:
            continue
        filas = [
            [
                f"<code>{html.escape(t['nombre'])}</code>",
                _descripcion_tabla(t["nombre"], t["comentario"], sec),
                f"{t['filas']:,}" if t["filas"] is not None else "—",
            ]
            for t in grupo
        ]
        partes.append(
            f'    <h3>{titulo}<span class="tag {clase}">{etiqueta}</span></h3>\n'
            + tabla_html(["Tabla", "Descripción", "Filas aprox."], filas, ["", "", "num"])
        )
    fecha = bd["consultado"].strftime("%-d de %B de %Y")
    partes.append(
        f'    <p class="note">Las cifras de filas se obtuvieron de la base de datos de '
        f"producción el {fecha}.</p>"
    )
    return tarjeta("🧱", "Tablas generadas", "\n".join(partes))


def seccion_vistas(sec: dict, bd: dict) -> str:
    if not bd["vistas"]:
        return ""
    alcances = {
        f[0].strip("` "): f[1] for f in filas_tabla(sec.get("Vistas", "")) if len(f) >= 2
    }
    filas = [
        [
            f"<code>{html.escape(v['nombre'])}</code>",
            html.escape(v["comentario"]) if v["comentario"]
            else enriquecer(alcances.get(v["nombre"], "Sin descripción registrada.")),
        ]
        for v in bd["vistas"]
    ]
    partes = [tabla_html(["Vista", "Descripción"], filas)]
    partes.append('    <h3 style="margin-top:20px;font-size:15px">Estructura de columnas por vista</h3>')
    for v in bd["vistas"]:
        cols = "\n".join(
            f"      <tr><td>{n}</td><td><code>{html.escape(nombre)}</code></td>"
            f"<td><span class=\"dtype\">{html.escape(tipo)}</span></td></tr>"
            for n, nombre, tipo in v["columnas"]
        )
        partes.append(
            f'    <details class="view-detail">\n'
            f'      <summary><code>{html.escape(v["nombre"])}</code>'
            f'<span class="vcnt">{len(v["columnas"])}&nbsp;columnas</span></summary>\n'
            f"      <table>\n"
            f"        <thead><tr><th>#</th><th>Atributo</th><th>Tipo de dato</th></tr></thead>\n"
            f"        <tbody>\n{cols}\n</tbody>\n      </table>\n    </details>"
        )
    return tarjeta("👁️", "Vistas", "\n".join(partes))


def seccion_variables(sec: dict) -> str:
    filas = [
        [f"<code>{html.escape(f[0].strip('` '))}</code>", enriquecer(f[1])]
        for f in filas_tabla(sec.get("Variables de entorno", ""))
        if len(f) >= 2
    ]
    if not filas:
        return ""
    return tarjeta(
        "⚙️",
        "Variables de entorno",
        '    <p class="muted">Variables requeridas para la ejecución del DAG y del pipeline.</p>\n'
        + tabla_html(["Variable", "Descripción"], filas),
    )


# Airflow reporta el disparo manual con su propia frase; los documentos ya
# publicados lo nombran "bajo demanda".
_SIN_PROGRAMA = {"never, external triggers only", "none", ""}


def _programacion(dag: dict) -> str:
    """Celda de programación: cron cuando lo hay, siempre en lenguaje humano."""
    resumen = (dag.get("programacion") or "").strip()
    detalle = (dag.get("detalle_programacion") or "").strip()
    if resumen.lower() in _SIN_PROGRAMA:
        celda = "Bajo demanda (on-demand)"
    elif detalle and detalle.lower() != resumen.lower():
        celda = (
            f"<code>{html.escape(resumen)}</code>"
            f"<div class='muted'>{html.escape(detalle)}</div>"
        )
    else:
        celda = html.escape(resumen or "Bajo demanda (on-demand)")
    if dag.get("pausado"):
        celda += " <span class='muted'>· pausado</span>"
    return celda


def seccion_dags(dags: list[dict]) -> str:
    if not dags:
        return ""
    filas = []
    for d in dags:
        desc = html.escape(d["descripcion"]) if d["descripcion"] else "<span class='muted'>—</span>"
        filas.append([f"<code>{html.escape(d['dag_id'])}</code>", desc, _programacion(d)])
    return tarjeta(
        "🌀",
        "DAGs",
        tabla_html(["DAG", "Descripción", "Programación"], filas, ["", "", "sched"]),
    )


def seccion_der(svg: str | None) -> str:
    if not svg:
        return ""
    ctrl = (
        '<div class="erd-ctrl"><button class="erd-btn" onclick="erdZoomIn()" title="Acercar">+</button>'
        '<button class="erd-btn" onclick="erdZoomOut()" title="Alejar">−</button>'
        '<button class="erd-btn" onclick="erdReset()" title="Ver todo">⊡</button></div>'
    )
    return tarjeta("🔗", "Diagrama entidad-relación", f'    <div class="erd">{ctrl}{svg}\n</div>')


# ── Navegación compartida por todos los documentos ────────────────────────


def etiquetas_existentes() -> dict[str, str]:
    """Etiqueta de barra lateral de cada pipeline, como ya está curada.

    No son el `<h1>` del documento: la columna es angosta y varias se abreviaron
    a mano («Estab. de Salud», «Pobreza Multidim.»). Se leen de la navegación ya
    publicada —que todos los documentos incrustan igual, así que sirve
    cualquiera y no hace falta señalar uno de referencia— y se completan con el
    `<h1>` de los documentos que esa navegación todavía no liste.
    """
    curadas: dict[str, str] = {}
    titulos: dict[str, str] = {}
    for archivo in sorted(docs_dir().glob("*.html")):
        if archivo.stem == "index":
            continue
        contenido = archivo.read_text(encoding="utf-8")
        if not curadas:
            curadas = {
                clave: html.unescape(texto)
                for clave, texto in re.findall(
                    r'<a class="sn-item[^"]*" href="([^"]+)\.html">([^<]+)</a>', contenido
                )
            }
        m = re.search(r"<h1>(.*?)</h1>", contenido, re.S)
        if m:
            titulos[archivo.stem] = html.unescape(m.group(1).strip())
    return {**titulos, **curadas}


def indice_pipelines(pendientes: list[str] | None = None) -> list[tuple[str, str]]:
    """Pipelines que tendrán documento, en el orden alfabético ya usado.

    La navegación enlaza archivos hermanos, así que se arma con los documentos
    que existen en el directorio más los que esta corrida está por escribir; un
    pipeline del inventario sin documento produciría un enlace roto.
    """
    etiquetas = etiquetas_existentes()
    claves = set(etiquetas) | set(pendientes or [])
    for clave in claves - set(etiquetas):
        etiquetas[clave] = nombres(clave)[0]
    return [(k, etiquetas[k]) for k in sorted(claves)]


def sidenav(actual: str, indice: list[tuple[str, str]]) -> str:
    filas = [
        f'  <a class="sn-item{" active" if k == actual else ""}" href="{k}.html">'
        f"{html.escape(etiqueta)}</a>"
        for k, etiqueta in indice
    ]
    return (
        '<nav class="sidenav">\n'
        '  <a class="sidenav-back" href="index.html">&#8592;&nbsp;Índice de pipelines</a>\n'
        '  <span class="sidenav-title">Pipelines ETL-SIEEJ</span>\n'
        + "\n".join(filas)
        + "\n</nav>"
    )


def prevnext(actual: str, indice: list[tuple[str, str]]) -> str:
    claves = [k for k, _ in indice]
    i = claves.index(actual)
    botones = []
    if i > 0:
        k, etiqueta = indice[i - 1]
        botones.append(f'<a class="nav-btn" href="{k}.html">&#8592; {html.escape(etiqueta)}</a>')
    if i < len(indice) - 1:
        k, etiqueta = indice[i + 1]
        botones.append(f'<a class="nav-btn" href="{k}.html">{html.escape(etiqueta)} &#8594;</a>')
    return f'<div class="prevnext">{"".join(botones)}</div>'


def actualizar_navegacion(indice: list[tuple[str, str]]) -> list[str]:
    """Reescribe barra lateral y anterior/siguiente en todos los documentos.

    Solo toca esos dos bloques: el contenido curado de los documentos que ya
    existían no se regenera.
    """
    tocados = []
    for clave, _ in indice:
        archivo = docs_dir() / f"{clave}.html"
        if not archivo.exists():
            continue
        s = archivo.read_text(encoding="utf-8")
        nuevo = re.sub(r'<nav class="sidenav">.*?</nav>', sidenav(clave, indice), s, flags=re.S)
        nuevo = re.sub(r'<div class="prevnext">.*?</div>', prevnext(clave, indice), nuevo, flags=re.S)
        if nuevo != s:
            archivo.write_text(nuevo, encoding="utf-8")
            tocados.append(clave)
    return tocados


# ── Documento completo ────────────────────────────────────────────────────


def hero(pipeline: str, sec: dict, indice: list[tuple[str, str]]) -> str:
    corto, producto = nombres(pipeline)
    caracteristicas = dict(
        (f[0], f[1]) for f in filas_tabla(sec.get("Características de los datos", "")) if len(f) >= 2
    )
    insignias = [f"BD: {pipeline}"]
    for clave in ("Frecuencia de actualización", "Desagregación"):
        if caracteristicas.get(clave):
            insignias.append(re.sub(r"[`*]", "", caracteristicas[clave]))
    for clave in ("Última fecha disponible", "Primer periodo disponible"):
        if caracteristicas.get(clave):
            etiqueta = "Última" if clave.startswith("Última") else "Desde"
            insignias.append(f"{etiqueta}: {re.sub(r'[`*]', '', caracteristicas[clave])}")
            break
    badges = "".join(f"<span class='badge'>{html.escape(b)}</span>" for b in insignias)
    return f"""<body>
<header class="hero">
  <div class="wrap">
    <div class="hero-logos"><img src="assets/logo_iieg.svg" alt="IIEG" class="hero-logo-iieg"><span class="hero-logo-sep"></span><img src="assets/logo_jal.svg" alt="Gobierno de Jalisco" class="hero-logo-jal"></div>
    <p class="hero-dir">Dirección del Sistema de Información</p>
    <p class="eyebrow">ETL-SIEEJ · Documentación de pipeline</p>
    <h1>{html.escape(corto)}</h1>
    <p class="dataset">{html.escape(producto)}</p>
    <div class="badges">{badges}</div>
    <div class="header-nav">
    <a class="back" href="index.html">&#8592; Índice de pipelines</a>
    {prevnext(pipeline, indice)}
  </div>
  </div>
</header>"""


def generar(pipeline: str, indice: list[tuple[str, str]]) -> Path:
    md = desde_git(f"core/pipelines/{pipeline}/README.md")
    if md is None:
        raise SystemExit(f"{pipeline}: sin README en {ref_git()} de ETL-SIEEJ")
    sec = secciones_readme(md)
    bd = datos_bd(pipeline)
    dags = datos_airflow(pipeline)
    cabecera, script = plantilla()
    corto, _ = nombres(pipeline)
    cabecera = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(corto)} — Documentación de pipeline ETL-SIEEJ</title>",
        cabecera,
        flags=re.S,
    )
    cuerpo = "".join(
        (
            seccion_descripcion(sec),
            seccion_fuente(pipeline, sec),
            seccion_tablas(sec, bd),
            seccion_vistas(sec, bd),
            seccion_variables(sec),
            seccion_dags(dags),
            seccion_der(svg_incrustable(pipeline)),
        )
    )
    pie = (
        "  <footer>\n    Documentación generada a partir del README homologado, las "
        "migraciones SQL y la base de datos de producción · ETL-SIEEJ · IIEG · "
        f"{bd['consultado'].strftime('%-d de %B de %Y')} · "
        f"README en {html.escape(ref_git())} {commit_referencia()}\n  </footer>"
    )
    doc = (
        cabecera
        + hero(pipeline, sec, indice)
        + '\n<div class="page-layout">\n'
        + sidenav(pipeline, indice)
        + '\n<div class="main-area">\n<div class="wrap">\n'
        + cuerpo
        + "\n"
        + pie
        + "\n</div>\n"
        + script
    )
    destino = docs_dir() / f"{pipeline}.html"
    destino.write_text(doc, encoding="utf-8")
    return destino


def main() -> int:
    for loc in ("es_MX.UTF-8", "es_ES.UTF-8", "es_MX", ""):
        try:
            locale.setlocale(locale.LC_TIME, loc)
            break
        except locale.Error:
            continue
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pipelines", nargs="*", help="pipelines a generar")
    ap.add_argument(
        "--todos-faltantes",
        action="store_true",
        help="genera los pipelines del inventario que aún no tienen documento",
    )
    ap.add_argument("--solo-navegacion", action="store_true", help="solo reescribe la navegación")
    args = ap.parse_args()

    if args.solo_navegacion:
        tocados = actualizar_navegacion(indice_pipelines())
        print(f"navegación actualizada en {len(tocados)} documentos")
        return 0

    if args.todos_faltantes:
        objetivo = pipelines_faltantes()
        if not objetivo:
            print("no hay pipelines sin documento en el inventario")
            return 0
        print(f"faltantes según el inventario: {', '.join(objetivo)}")
    else:
        objetivo = args.pipelines
    if not objetivo:
        ap.error("indica pipelines o usa --todos-faltantes")

    indice = indice_pipelines(objetivo)
    for p in objetivo:
        destino = generar(p, indice)
        print(f"  {p}: {destino.name} ({destino.stat().st_size / 1024:.0f} KB)")
    tocados = actualizar_navegacion(indice)
    print(f"navegación actualizada en {len(tocados)} documentos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
