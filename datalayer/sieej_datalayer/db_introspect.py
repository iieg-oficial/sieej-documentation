"""Introspección de solo lectura de la BD de producción (PostgreSQL/PostGIS).

Toda conexión se abre con `default_transaction_read_only=on` (ver config) y
solo se consultan catálogos (`pg_views`, `pg_matviews`, `pg_class`) y conteos.
"""

from datetime import datetime, timezone

from psycopg import sql

from .config import Settings
from .models import (
    BaseDeDatos,
    Columna,
    ColumnaTabla,
    EstadoFuente,
    Fuente,
    Relacion,
    Tabla,
    Vista,
)

# Vistas creadas por PostGIS en cada base; no son producto de un pipeline.
VISTAS_SISTEMA_POSTGIS = {"geometry_columns", "geography_columns", "raster_columns"}

SQL_BASES = """
SELECT datname
  FROM pg_database
 WHERE NOT datistemplate
   AND datallowconn
   AND datname NOT IN ('postgres')
   AND has_database_privilege(datname, 'CONNECT')
 ORDER BY datname
"""

# Lo que instala una extensión (PostGIS publica `spatial_ref_sys`) no es del
# pipeline: se excluye por pertenencia a la extensión, no por lista de nombres.
SQL_TABLAS = """
SELECT c.relname, obj_description(c.oid, 'pg_class')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
   AND c.relname <> 'flyway_schema_history'
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
 ORDER BY c.relname
"""

SQL_COLUMNAS_TABLA = """
SELECT a.attname,
       pg_catalog.format_type(a.atttypid, a.atttypmod),
       COALESCE(a.attnum = ANY(pk.conkey), false),
       NOT a.attnotnull
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid
  LEFT JOIN pg_constraint pk ON pk.conrelid = c.oid AND pk.contype = 'p'
 WHERE n.nspname = 'public' AND c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY a.attnum
"""

SQL_RELACIONES = """
SELECT c.relname,
       ARRAY(SELECT attname FROM unnest(k.conkey) WITH ORDINALITY u(n, i)
               JOIN pg_attribute ON attrelid = k.conrelid AND attnum = u.n ORDER BY u.i),
       r.relname,
       ARRAY(SELECT attname FROM unnest(k.confkey) WITH ORDINALITY u(n, i)
               JOIN pg_attribute ON attrelid = k.confrelid AND attnum = u.n ORDER BY u.i)
  FROM pg_constraint k
  JOIN pg_class c ON c.oid = k.conrelid
  JOIN pg_class r ON r.oid = k.confrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE k.contype = 'f' AND n.nspname = 'public'
 ORDER BY c.relname, k.conname
"""

SQL_DESCRIPCION = """
SELECT obj_description(c.oid, 'pg_class')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = %s AND c.relname = %s
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
        cur.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(esquema), sql.Identifier(nombre)
            )
        )
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
        cur.execute(SQL_DESCRIPCION, (esquema, vista))
        fila = cur.fetchone()
        vistas.append(
            Vista(
                esquema=esquema,
                nombre=vista,
                tipo=tipo,
                descripcion=fila[0] if fila else None,
                registros=_contar_registros(cur, esquema, vista, timeout_ms),
                columnas=columnas,
                en_bd=True,
            )
        )
    tablas: list[Tabla] = []
    cur.execute(SQL_TABLAS)
    for tabla, descripcion in cur.fetchall():
        cur.execute(SQL_COLUMNAS_TABLA, (tabla,))
        columnas = [
            ColumnaTabla(nombre=col, tipo=tipo_dato, pk=bool(pk), nullable=bool(nulo))
            for col, tipo_dato, pk, nulo in cur.fetchall()
        ]
        tablas.append(
            Tabla(
                nombre=tabla,
                descripcion=descripcion,
                filas=_contar_registros(cur, "public", tabla, timeout_ms),
                columnas=columnas,
            )
        )
    cur.execute(SQL_RELACIONES)
    relaciones = [
        Relacion(tabla=t, columnas=list(cols), ref_tabla=rt, ref_columnas=list(rcols))
        for t, cols, rt, rcols in cur.fetchall()
    ]
    return BaseDeDatos(
        nombre=nombre,
        es_infraestructura=bool(filas) and solo_sistema,
        vistas=vistas,
        tablas=tablas,
        relaciones=relaciones,
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
        fallidas: list[str] = []
        for nombre in nombres:
            try:
                with connect(**settings.pg_conninfo(nombre)) as conn:
                    bases.append(introspectar_base(conn, nombre, settings.pg_count_timeout_ms))
            except Exception:
                fallidas.append(nombre)
        if not bases:
            detalle = "Ninguna base respondió" + (f": {', '.join(fallidas)}" if fallidas else "")
            return Fuente(estado=EstadoFuente.CAIDA, detalle=detalle), []
        detalle = f"{len(bases)} bases de datos"
        if fallidas:
            detalle += f"; sin acceso: {', '.join(fallidas)}"
        fuente = Fuente(
            estado=EstadoFuente.OK,
            consultado_en=datetime.now(timezone.utc),
            detalle=detalle,
        )
        return fuente, bases
    except Exception as exc:
        return Fuente(estado=EstadoFuente.CAIDA, detalle=f"{type(exc).__name__}: {exc}"), []
