"""Introspección de solo lectura de la BD de producción (PostgreSQL/PostGIS).

Toda conexión se abre con `default_transaction_read_only=on` (ver config) y
solo se consultan catálogos (`pg_views`, `pg_matviews`, `pg_class`) y conteos.
"""

from datetime import datetime, timezone

from .config import Settings
from .models import BaseDeDatos, Columna, EstadoFuente, Fuente, Vista

# Vistas creadas por PostGIS en cada base; no son producto de un pipeline.
VISTAS_SISTEMA_POSTGIS = {"geometry_columns", "geography_columns", "raster_columns"}

SQL_BASES = """
SELECT datname
  FROM pg_database
 WHERE NOT datistemplate
   AND datname NOT IN ('postgres')
 ORDER BY datname
"""

SQL_VISTAS = """
SELECT schemaname, viewname AS nombre, 'VIEW' AS tipo
  FROM pg_views
 WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT schemaname, matviewname AS nombre, 'MATERIALIZED VIEW' AS tipo
  FROM pg_matviews
 WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
 ORDER BY 1, 2
"""

# information_schema.columns no incluye vistas materializadas; pg_attribute sí.
SQL_COLUMNAS = """
SELECT a.attnum,
       a.attname,
       pg_catalog.format_type(a.atttypid, a.atttypmod) AS tipo,
       NOT a.attnotnull AS nullable,
       pg_catalog.col_description(c.oid, a.attnum) AS descripcion
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
 WHERE n.nspname = %s
   AND c.relname = %s
   AND a.attnum > 0
   AND NOT a.attisdropped
 ORDER BY a.attnum
"""

SQL_CONTEO_ESTIMADO = """
SELECT GREATEST(c.reltuples, 0)::bigint
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = %s AND c.relname = %s
"""


def _contar_registros(cur, esquema: str, nombre: str, timeout_ms: int) -> int | None:
    """COUNT(*) exacto con timeout; si excede, cae al estimado del catálogo."""
    try:
        cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
        cur.execute(f'SELECT count(*) FROM "{esquema}"."{nombre}"')
        return int(cur.fetchone()[0])
    except Exception:
        try:
            cur.execute("ROLLBACK")
            cur.execute(SQL_CONTEO_ESTIMADO, (esquema, nombre))
            fila = cur.fetchone()
            return int(fila[0]) if fila else None
        except Exception:
            return None


def introspectar_base(conn, nombre: str, timeout_ms: int = 30000) -> BaseDeDatos:
    """Estructura completa de una base: vistas/matviews con columnas y conteos."""
    cur = conn.cursor()
    cur.execute(SQL_VISTAS)
    filas = cur.fetchall()
    vistas: list[Vista] = []
    solo_sistema = True
    for esquema, vista, tipo in filas:
        if vista not in VISTAS_SISTEMA_POSTGIS:
            solo_sistema = False
        cur.execute(SQL_COLUMNAS, (esquema, vista))
        columnas = [
            Columna(
                posicion=attnum,
                nombre=attname,
                tipo=tipo_dato,
                nullable=bool(nullable),
                descripcion=descripcion,
                origen_descripcion="bd" if descripcion else None,
            )
            for attnum, attname, tipo_dato, nullable, descripcion in cur.fetchall()
        ]
        vistas.append(
            Vista(
                esquema=esquema,
                nombre=vista,
                tipo=tipo,
                registros=_contar_registros(cur, esquema, vista, timeout_ms),
                columnas=columnas,
                en_bd=True,
            )
        )
    return BaseDeDatos(
        nombre=nombre,
        es_infraestructura=bool(filas) and solo_sistema,
        vistas=vistas,
    )


def consultar_bd(settings: Settings, connect=None) -> tuple[Fuente, list[BaseDeDatos]]:
    """Introspecta todas las bases de producción; nunca lanza.

    `connect` es inyectable para pruebas; por defecto usa `psycopg.connect`.
    """
    if not settings.pg_configurado:
        return (
            Fuente(
                estado=EstadoFuente.SIN_CONFIGURAR,
                detalle="Faltan PG_HOST/PG_USER/PG_PASSWORD",
            ),
            [],
        )
    if connect is None:
        import psycopg

        connect = psycopg.connect
    try:
        with connect(**settings.pg_conninfo(settings.pg_maintenance_db)) as conn:
            cur = conn.cursor()
            cur.execute(SQL_BASES)
            nombres = [fila[0] for fila in cur.fetchall()]
        bases: list[BaseDeDatos] = []
        for nombre in nombres:
            with connect(**settings.pg_conninfo(nombre)) as conn:
                bases.append(introspectar_base(conn, nombre, settings.pg_count_timeout_ms))
        fuente = Fuente(
            estado=EstadoFuente.OK,
            consultado_en=datetime.now(timezone.utc),
            detalle=f"{len(bases)} bases de datos",
        )
        return fuente, bases
    except Exception as exc:
        return Fuente(estado=EstadoFuente.CAIDA, detalle=f"{type(exc).__name__}: {exc}"), []
