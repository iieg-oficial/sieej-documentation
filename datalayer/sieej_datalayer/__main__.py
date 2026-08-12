"""CLI: `python -m sieej_datalayer` regenera data/*.json desde las fuentes.

Sale siempre con código 0: la falta de fuentes vivas degrada, nunca rompe.
"""

import json
import sys

from .config import Settings
from .generate import generar_y_escribir


def main() -> int:
    settings = Settings()
    acciones = generar_y_escribir(settings)
    reporte = {
        "data_dir": str(settings.data_dir),
        "airflow_configurado": settings.airflow_configurado,
        "pg_configurado": settings.pg_configurado,
        "acciones": acciones,
    }
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
