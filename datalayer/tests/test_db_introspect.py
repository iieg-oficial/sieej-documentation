from sieej_datalayer import db_introspect
from sieej_datalayer.config import Settings
from sieej_datalayer.db_introspect import consultar_bd, introspectar_base
from sieej_datalayer.models import EstadoFuente

CATALOGO = {
    "postgres": {"bases": ["cvegeo", "denue"]},
    "denue": {
        "vistas": [("public", "v_establecimientos", "VIEW")],
        "columnas": {
            ("public", "v_establecimientos"): [
                (1, "id", "integer", False, None),
                (2, "municipio", "character varying", True, "Municipio de Jalisco"),
            ]
        },
        "conteos": {("public", "v_establecimientos"): 1500},
    },
    "cvegeo": {
        "vistas": [
            ("public", "geometry_columns", "VIEW"),
            ("public", "geography_columns", "VIEW"),
        ],
        "columnas": {},
        "conteos": {},
    },
}


class FakeCursor:
    def __init__(self, db: dict, count_fails: bool = False):
        self._db = db
        self._count_fails = count_fails
        self._result: list[tuple] = []

    def execute(self, sql: str, params: tuple = ()):
        sql = sql.strip()
        if sql == db_introspect.SQL_BASES.strip():
            self._result = [(n,) for n in self._db["bases"]]
        elif sql == db_introspect.SQL_VISTAS.strip():
            self._result = list(self._db["vistas"])
        elif sql == db_introspect.SQL_COLUMNAS.strip():
            self._result = list(self._db["columnas"].get(tuple(params), []))
        elif sql.startswith("SELECT count(*)"):
            if self._count_fails:
                raise TimeoutError("statement timeout")
            esquema, nombre = _parse_ident(sql)
            self._result = [(self._db["conteos"].get((esquema, nombre), 0),)]
        elif sql == db_introspect.SQL_CONTEO_ESTIMADO.strip():
            self._result = [(99,)]
        else:  # SET LOCAL, ROLLBACK…
            self._result = []

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None


def _parse_ident(sql: str) -> tuple[str, str]:
    resto = sql.split("FROM", 1)[1].strip()
    esquema, nombre = resto.split(".", 1)
    return esquema.strip('" '), nombre.strip('" ')


class FakeConnection:
    def __init__(self, db: dict, count_fails: bool = False):
        self._cursor = FakeCursor(db, count_fails)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_connect(count_fails: bool = False):
    def connect(**kwargs):
        return FakeConnection(CATALOGO[kwargs["dbname"]], count_fails)

    return connect


def _settings() -> Settings:
    return Settings(_env_file=None, pg_host="db.test", pg_user="ro", pg_password="x")


def test_introspeccion_completa():
    fuente, bases = consultar_bd(_settings(), connect=fake_connect())
    assert fuente.estado is EstadoFuente.OK
    assert [b.nombre for b in bases] == ["cvegeo", "denue"]
    denue = bases[1]
    assert not denue.es_infraestructura
    vista = denue.vistas[0]
    assert vista.tipo == "VIEW"
    assert vista.registros == 1500
    assert vista.en_bd is True
    assert [c.nombre for c in vista.columnas] == ["id", "municipio"]
    assert vista.columnas[0].nullable is False
    assert vista.columnas[1].descripcion == "Municipio de Jalisco"
    assert vista.columnas[1].origen_descripcion == "bd"


def test_base_solo_postgis_es_infraestructura():
    fuente, bases = consultar_bd(_settings(), connect=fake_connect())
    cvegeo = bases[0]
    assert cvegeo.es_infraestructura


def test_conteo_cae_al_estimado_si_count_excede_timeout():
    conn = FakeConnection(CATALOGO["denue"], count_fails=True)
    base = introspectar_base(conn, "denue")
    assert base.vistas[0].registros == 99


def test_sin_configurar_no_conecta():
    fuente, bases = consultar_bd(Settings(_env_file=None))
    assert fuente.estado is EstadoFuente.SIN_CONFIGURAR
    assert bases == []


def test_fuente_caida_no_lanza():
    def connect(**kwargs):
        raise ConnectionRefusedError("sin ruta al host")

    fuente, bases = consultar_bd(_settings(), connect=connect)
    assert fuente.estado is EstadoFuente.CAIDA
    assert bases == []
