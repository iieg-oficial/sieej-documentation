#!/bin/sh
set -u

INTERVALO="${REBUILD_INTERVAL_SECONDS:-86400}"

sincronizar() {
    echo "[sincronizador] $(date -Iseconds) leyendo BD, Airflow y README…"
    /venv/bin/python -m sieej_datalayer || echo "[sincronizador] el datalayer reportó error; se conservan los datos previos"
    date -Iseconds > /app/data/.ultima-corrida
    echo "[sincronizador] $(date -Iseconds) ciclo terminado"
}

if [ "${1:-}" = "una-vez" ]; then
    sincronizar
    exit
fi

while :; do
    sincronizar
    sleep "$INTERVALO"
done
