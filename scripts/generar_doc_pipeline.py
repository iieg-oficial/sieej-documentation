#!/usr/bin/env python3
"""Genera la documentación HTML de un pipeline, homologada a las existentes.

Toma como fuentes las mismas tres que declara el pie de los documentos ya
publicados: el README del pipeline en ETL-SIEEJ, el diagrama entidad-relación
del propio repositorio, y la base de datos de producción (conteos exactos,
comentarios de tabla y estructura de columnas de cada vista). La programación
de los DAG se lee de la API de Airflow.

El estilo no se reescribe: se copia literal del `<head>` y del `<script>` de un
documento existente, de modo que los nuevos no puedan divergir del formato.

Uso:
    .venv/bin/python scripts/generar_doc_pipeline.py emec ems           # algunos
    .venv/bin/python scripts/generar_doc_pipeline.py --todos-faltantes  # los 10
    .venv/bin/python scripts/generar_doc_pipeline.py --solo-navegacion  # nav
"""

from __future__ import annotations

import argparse
import html
import locale
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ETL = Path.home() / "Documents/IIEG/sieej/ETL-SIEEJ"
DOCS = Path.home() / "Documents/IIEG/sieej/general-documentation/etls-pipelines-readmes/html-documents"
REF_GIT = "origin/main"
REFERENCIA = "denue.html"

# Nombre corto (barra lateral y título) y nombre del producto (subtítulo del
# hero). El README no los expone en un campo propio, así que se curan aquí.
NOMBRES: dict[str, tuple[str, str]] = {
    "defunciones": ("Defunciones", "Registro de defunciones generales — DGIS"),
    "emec": ("EMEC", "Encuesta Mensual sobre Empresas Comerciales"),
    "emim": ("EMIM", "Encuesta Mensual de la Industria Manufacturera"),
    "ems": ("EMS", "Encuesta Mensual de Servicios"),
    "enec": ("ENEC", "Encuesta Nacional de Empresas Constructoras"),
    "enoe": ("ENOE", "Encuesta Nacional de Ocupación y Empleo"),
    "enoe_microdatos": ("ENOE Microdatos", "ENOE — microdatos completos (SDEM + COE1 + COE2)"),
    "indice_shf_vivienda": ("Índice SHF Vivienda", "Índice SHF de Precios de la Vivienda en México"),
    "rastros": ("Rastros (ESGRM)", "Sacrificio de Ganado en Rastros Municipales"),
    "scian": ("SCIAN", "Sistema de Clasificación Industrial de América del Norte 2023"),
}

FALTANTES = list(NOMBRES)


# ── Lectura de las fuentes ─────────────────────────────────────────────────


def desde_git(ruta: str) -> str | None:
    """Contenido de un archivo en la rama de referencia de ETL-SIEEJ."""
    r = subprocess.run(
        ["git", "show", f"{REF_GIT}:{ruta}"],
        cwd=REPO_ETL,
        capture_output=True,
        text=True,
    )
    return r.stdout if r.returncode == 0 else None


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

SQL_TABLAS = """
SELECT c.relname, obj_description(c.oid)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
   AND c.relname <> 'flyway_schema_history'
 ORDER BY c.relname
"""

SQL_VISTAS = """
SELECT c.relname, c.relkind, obj_description(c.oid)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm')
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

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "datalayer"))
    from sieej_datalayer.config import Settings

    s = Settings()
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
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "datalayer"))
    from sieej_datalayer.airflow_client import AirflowClient
    from sieej_datalayer.config import Settings
    from sieej_datalayer.crosscheck import partir_dag_id

    s = Settings()
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
    """Devuelve (cabecera hasta <body>, script final) del documento modelo."""
    s = (DOCS / REFERENCIA).read_text(encoding="utf-8")
    cabecera = s[: s.index("<body>")]
    script = s[s.index("<script>") :]
    return cabecera, script


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
    corto, producto = NOMBRES[pipeline]
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
    """Nombre corto de cada pipeline, tal como ya aparece en la barra lateral."""
    s = (DOCS / REFERENCIA).read_text(encoding="utf-8")
    pares = re.findall(r'<a class="sn-item[^"]*" href="([^"]+)\.html">([^<]+)</a>', s)
    return {clave: html.unescape(texto) for clave, texto in pares}


def indice_pipelines() -> list[tuple[str, str]]:
    """Todos los pipelines con documento, en el orden alfabético ya usado."""
    etiquetas = etiquetas_existentes()
    etiquetas.update({k: v[0] for k, v in NOMBRES.items()})
    claves = sorted(
        p.stem for p in DOCS.glob("*.html") if p.stem != "index"
    ) or sorted(etiquetas)
    for k in NOMBRES:
        if k not in claves:
            claves.append(k)
    return [(k, etiquetas.get(k, k.replace("_", " ").title())) for k in sorted(set(claves))]


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
        archivo = DOCS / f"{clave}.html"
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
    corto, producto = NOMBRES[pipeline]
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
        raise SystemExit(f"{pipeline}: sin README en {REF_GIT} de ETL-SIEEJ")
    sec = secciones_readme(md)
    bd = datos_bd(pipeline)
    dags = datos_airflow(pipeline)
    cabecera, script = plantilla()
    corto, _ = NOMBRES[pipeline]
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
        f"{bd['consultado'].strftime('%-d de %B de %Y')}\n  </footer>"
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
    destino = DOCS / f"{pipeline}.html"
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
    ap.add_argument("--todos-faltantes", action="store_true", help=f"genera: {', '.join(FALTANTES)}")
    ap.add_argument("--solo-navegacion", action="store_true", help="solo reescribe la navegación")
    args = ap.parse_args()

    indice = indice_pipelines()
    if args.solo_navegacion:
        tocados = actualizar_navegacion(indice)
        print(f"navegación actualizada en {len(tocados)} documentos")
        return 0

    objetivo = FALTANTES if args.todos_faltantes else args.pipelines
    if not objetivo:
        ap.error("indica pipelines o usa --todos-faltantes")
    for p in objetivo:
        destino = generar(p, indice)
        print(f"  {p}: {destino.name} ({destino.stat().st_size / 1024:.0f} KB)")
    tocados = actualizar_navegacion(indice)
    print(f"navegación actualizada en {len(tocados)} documentos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
