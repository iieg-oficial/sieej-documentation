from pathlib import Path

from sieej_datalayer.config import Settings


def _settings(**kwargs) -> Settings:
    # _env_file=None evita que un .env local contamine los tests
    return Settings(_env_file=None, **kwargs)


def test_fuentes_sin_configurar_por_defecto():
    s = _settings()
    assert not s.airflow_configurado
    assert not s.pg_configurado


def test_airflow_configurado_requiere_credenciales_completas():
    s = _settings(airflow_base_url="http://airflow:8080")
    assert not s.airflow_configurado
    s = _settings(
        airflow_base_url="http://airflow:8080",
        airflow_username="viewer",
        airflow_password="x",
    )
    assert s.airflow_configurado


def test_pg_conninfo_es_solo_lectura():
    s = _settings(pg_host="db", pg_user="ro", pg_password="x")
    assert s.pg_configurado
    info = s.pg_conninfo("denue")
    assert info["dbname"] == "denue"
    assert "default_transaction_read_only=on" in info["options"]


def test_data_dir_por_defecto():
    assert _settings().data_dir == Path("data")
