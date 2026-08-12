"""Configuración por variables de entorno (nunca credenciales en código)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Airflow (API REST, usuario de solo lectura)
    airflow_base_url: str | None = None
    airflow_username: str | None = None
    airflow_password: str | None = None
    airflow_timeout: float = 15.0
    airflow_recent_runs: int = 20

    # PostgreSQL de producción (usuario de solo lectura)
    pg_host: str | None = None
    pg_port: int = 5432
    pg_user: str | None = None
    pg_password: str | None = None
    pg_maintenance_db: str = "postgres"
    pg_connect_timeout: int = 15
    pg_count_timeout_ms: int = 30000

    # Documentación estática (generada fuera de este repositorio)
    docs_html_dir: Path | None = None
    views_md_dir: Path | None = None

    # Salida
    data_dir: Path = Path("data")

    @property
    def airflow_configurado(self) -> bool:
        return bool(self.airflow_base_url and self.airflow_username and self.airflow_password)

    @property
    def pg_configurado(self) -> bool:
        return bool(self.pg_host and self.pg_user and self.pg_password)

    def pg_conninfo(self, dbname: str) -> dict:
        """Parámetros de conexión psycopg para una base dada, siempre de solo lectura."""
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "user": self.pg_user,
            "password": self.pg_password,
            "dbname": dbname,
            "connect_timeout": self.pg_connect_timeout,
            # Candado duro: cualquier escritura accidental falla en el servidor.
            "options": "-c default_transaction_read_only=on",
        }
