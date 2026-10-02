"""Documentación de cada pipeline, leída de su README en ETL-SIEEJ.

El builder mantiene un clon superficial de ETL-SIEEJ con solo `core/pipelines`
y lo actualiza en cada ciclo. Del README salen el texto y la ficha de la
fuente; lo que existe en producción lo dicen la BD y Airflow, nunca el README.
"""

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .models import Descarga, DocumentoPipeline, EstadoFuente, Fuente, Par

# Nombres que difieren entre fuentes: la BD usa singular donde ETL-SIEEJ y los
# DAG de Airflow usan plural. Se aplica tanto a las carpetas como a los DAG.
ALIAS_NOMBRE_A_BD = {"censos_economicos": "censo_economico"}

CARPETA_PIPELINES = "core/pipelines"

# Título corto y nombre del producto. El README no los expone en un campo
# propio; estos son los que ya se publicaban en los documentos de pipeline.
NOMBRES: dict[str, tuple[str, str]] = {
    "agropecuario_siap": ("Agropecuario SIAP", "Estadística de producción agrícola municipal"),
    "asg_imss": ("ASG IMSS", "Asegurados, Salarios y Grupos de cotización del IMSS"),
    "censo_poblacion": ("Censo de Población", "Censo de Población y Vivienda (ITER / Intercensal)"),
    "censos_economicos": ("Censos Económicos", "Censos Económicos"),
    "centros_educativos": (
        "Centros Educativos (SIGED)",
        "Catálogo de centros de trabajo educativos",
    ),
    "conapo": ("CONAPO", "Proyecciones de Población Municipal — Jalisco"),
    "datamexico": (
        "DataMéxico — Comercio Exterior",
        "Flujos de comercio exterior (importaciones/exportaciones)",
    ),
    "defunciones": ("Defunciones", "Registro de defunciones generales — DGIS"),
    "defunciones_inegi": ("Defunciones (INEGI)", "Estadísticas de Defunciones Registradas — EDR"),
    "delitos_fuero_comun": (
        "Delitos del Fuero Común",
        "Incidencia delictiva del fuero común (municipal)",
    ),
    "denue": ("DENUE", "Directorio Estadístico Nacional de Unidades Económicas"),
    "edafologia": ("Edafología", "Edafología histórica 1:250 000, Serie III — INEGI"),
    "efipem": ("EFIPEM", "Estadísticas de Finanzas Públicas Estatales y Municipales"),
    "emec": ("EMEC", "Encuesta Mensual sobre Empresas Comerciales"),
    "emim": ("EMIM", "Encuesta Mensual de la Industria Manufacturera"),
    "ems": ("EMS", "Encuesta Mensual de Servicios"),
    "enec": ("ENEC", "Encuesta Nacional de Empresas Constructoras"),
    "enoe": ("ENOE", "Encuesta Nacional de Ocupación y Empleo"),
    "enoe_microdatos": ("ENOE Microdatos", "ENOE — microdatos completos (SDEM + COE1 + COE2)"),
    "escuelas": ("Escuelas", "Directorio y estadística de escuelas de Jalisco"),
    "establecimientos_de_salud": (
        "Establecimientos de Salud (CLUES)",
        "Catálogo de Establecimientos de Salud (CLUES)",
    ),
    "etef": ("ETEF", "Estadísticas de la Industria de Exportación"),
    "fiscalia": ("Fiscalía Jalisco", "Carpetas de investigación / denuncias"),
    "ilmm": ("ILMM", "Indicadores del Mercado Laboral a Nivel Municipal"),
    "indice_shf_vivienda": (
        "Índice SHF Vivienda",
        "Índice SHF de Precios de la Vivienda en México",
    ),
    "inpc": ("INPC", "Índice Nacional de Precios al Consumidor"),
    "intensidad_migratoria": (
        "Intensidad Migratoria",
        "Índice de Intensidad Migratoria México-EUA",
    ),
    "marginacion": ("Marginación", "Índice de Marginación"),
    "participacion_ciudadana": (
        "Participación Ciudadana",
        "Participación electoral ciudadana municipal",
    ),
    "pobreza_multidimensional": (
        "Pobreza Multidimensional",
        "Indicadores de pobreza multidimensional municipal",
    ),
    "produccion_ganadera": (
        "Producción Ganadera SIAP",
        "Estadística de producción ganadera municipal",
    ),
    "rastros": ("Rastros (ESGRM)", "Sacrificio de Ganado en Rastros Municipales"),
    "repd": ("REPD", "Registro Estatal de Personas Desaparecidas"),
    "scian": ("SCIAN", "Sistema de Clasificación Industrial de América del Norte 2023"),
}


def nombres(carpeta: str) -> tuple[str, str]:
    """Título y producto; un pipeline nuevo sin curar cae a un nombre derivado."""
    if carpeta in NOMBRES:
        return NOMBRES[carpeta]
    derivado = carpeta.replace("_", " ").title()
    return derivado, derivado


def _git(args: list[str], cwd: Path | None = None) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=180, check=True
    )
    return resultado.stdout.strip()


def sincronizar_clon(settings: Settings) -> str:
    """Clona o actualiza ETL-SIEEJ con solo `core/pipelines`; regresa el commit.

    Sin URL configurada se usa el clon tal como esté (útil en desarrollo).
    """
    destino = Path(settings.etl_repo_dir)
    if settings.etl_repo_url:
        if not (destino / ".git").is_dir():
            destino.mkdir(parents=True, exist_ok=True)
            _git(
                [
                    "clone", "--depth", "1", "--single-branch", "--branch",
                    settings.etl_repo_rama, "--sparse", settings.etl_repo_url, str(destino),
                ]
            )
            _git(["sparse-checkout", "set", CARPETA_PIPELINES], cwd=destino)
        else:
            _git(["fetch", "--depth", "1", "origin", settings.etl_repo_rama], cwd=destino)
            _git(["reset", "--hard", "FETCH_HEAD"], cwd=destino)
    return _git(["rev-parse", "--short", "HEAD"], cwd=destino)


def secciones(md: str, nivel: int = 2) -> dict[str, str]:
    """Parte el markdown en sus secciones de un nivel de encabezado dado."""
    patron = re.compile(rf"^{'#' * nivel}\s+(.+?)\s*$")
    partes: dict[str, str] = {}
    actual, buffer = None, []
    for linea in md.splitlines():
        m = patron.match(linea)
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


def citas(texto: str) -> list[str]:
    """Bloques de cita (`>`) del texto: son las advertencias del README."""
    return [
        " ".join(linea.lstrip("> ").strip() for linea in bloque.splitlines())
        for bloque in re.split(r"\n\s*\n", texto)
        if bloque.strip().startswith(">")
    ]


def _limpiar(celda: str) -> str:
    return celda.strip().strip("`").strip()


def parsear_readme(carpeta: str, md: str, commit: str | None = None) -> DocumentoPipeline:
    sec = secciones(md)
    titulo, producto = nombres(carpeta)
    general = sec.get("Descripción general", "")

    descargas = []
    especifica = re.search(r"```[a-z]*\n(.*?)```", sec.get("Fuente específica", ""), re.S)
    if especifica:
        for linea in especifica.group(1).strip().splitlines():
            variable, igual, url = linea.partition("=")
            if igual and url.strip().startswith("http"):
                descargas.append(Descarga(variable=variable.strip(), url=url.strip()))

    diccionario = secciones(sec.get("Diccionario de variables", ""), 3)
    descripcion_tablas: dict[str, str] = {}
    for titulo_sub, cuerpo in diccionario.items():
        primero = parrafos(cuerpo, 1)
        if primero:
            descripcion_tablas[_limpiar(titulo_sub)] = primero[0]
    for fila in filas_tabla(diccionario.get("Catálogos", "")):
        if len(fila) >= 2:
            descripcion_tablas.setdefault(_limpiar(fila[0]), fila[1])

    general_fuente = parrafos(sec.get("Fuente general", ""), 1)
    return DocumentoPipeline(
        nombre=ALIAS_NOMBRE_A_BD.get(carpeta, carpeta),
        carpeta=carpeta,
        titulo=titulo,
        producto=producto,
        descripcion=parrafos(general, 3),
        avisos=citas(general),
        caracteristicas=[
            Par(etiqueta=f[0], valor=f[1])
            for f in filas_tabla(sec.get("Características de los datos", ""))
            if len(f) >= 2
        ],
        fuente_general=general_fuente[0] if general_fuente else None,
        descargas=descargas[:2],
        variables=[
            Par(etiqueta=_limpiar(f[0]), valor=f[1])
            for f in filas_tabla(sec.get("Variables de entorno", ""))
            if len(f) >= 2
        ],
        descripcion_tablas=descripcion_tablas,
        alcance_vistas={
            _limpiar(f[0]): f[1] for f in filas_tabla(sec.get("Vistas", "")) if len(f) >= 2
        },
        commit=commit,
    )


def listar_carpetas(settings: Settings) -> dict[str, str]:
    """Carpetas de pipeline en el clon, tengan o no README: nombre de BD -> carpeta."""
    if not settings.etl_repo_dir:
        return {}
    raiz = Path(settings.etl_repo_dir) / CARPETA_PIPELINES
    if not raiz.is_dir():
        return {}
    return {
        ALIAS_NOMBRE_A_BD.get(d.name, d.name): d.name
        for d in sorted(raiz.iterdir())
        if d.is_dir() and not d.name.startswith((".", "_"))
    }


def leer_documentos(settings: Settings) -> tuple[Fuente, dict[str, DocumentoPipeline]]:
    """Documentos por nombre de pipeline (ya con alias de BD); nunca lanza.

    Un clon sin README cuenta como caída: cero documentos no es un estado sano
    y no debe sobrescribir un inventario bueno.
    """
    if not settings.etl_repo_dir:
        return Fuente(estado=EstadoFuente.SIN_CONFIGURAR, detalle="Falta ETL_REPO_DIR"), {}
    aviso = None
    commit = None
    try:
        commit = sincronizar_clon(settings)
    except Exception as exc:
        aviso = f"no se pudo actualizar el clon ({type(exc).__name__}); se usa el existente"
    raiz = Path(settings.etl_repo_dir) / CARPETA_PIPELINES
    documentos: dict[str, DocumentoPipeline] = {}
    if raiz.is_dir():
        for readme in sorted(raiz.glob("*/README.md")):
            doc = parsear_readme(
                readme.parent.name, readme.read_text(encoding="utf-8", errors="replace"), commit
            )
            documentos[doc.nombre] = doc
    if not documentos:
        return Fuente(estado=EstadoFuente.CAIDA, detalle=aviso or f"Sin README en {raiz}"), {}
    detalle = f"{len(documentos)} README de ETL-SIEEJ" + (f" @ {commit}" if commit else "")
    if aviso:
        detalle += f"; {aviso}"
    return (
        Fuente(estado=EstadoFuente.OK, consultado_en=datetime.now(timezone.utc), detalle=detalle),
        documentos,
    )
