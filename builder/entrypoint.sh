#!/bin/sh
# Reconstrucción periódica del sitio: datos primero, Astro después.
# Nunca deja el volumen a medias: si el build falla, se conserva el sitio previo.
set -u

INTERVALO="${REBUILD_INTERVAL_SECONDS:-86400}"

construir() {
    echo "[builder] $(date -Iseconds) regenerando data/*.json…"
    /venv/bin/python -m sieej_datalayer || echo "[builder] datalayer reportó error; se continúa con los datos previos"

    echo "[builder] construyendo el sitio…"
    if (cd /app/web && npm run build); then
        rsync -a --delete /app/web/dist/ /sitio/
        echo "[builder] $(date -Iseconds) sitio publicado en /sitio"
    else
        echo "[builder] el build de Astro falló; se conserva el sitio previo"
        return 1
    fi
}

construir

while :; do
    sleep "$INTERVALO"
    construir
done
