#!/usr/bin/env bash
# Abre un túnel SSH local hacia la BD de producción (postgis_db en iieg-db-etl).
#
# Solo Postgres necesita túnel. La API de Airflow es alcanzable directo por IP
# desde la red del IIEG y se consulta por HTTP sin intermediarios: apunta
# AIRFLOW_BASE_URL a http://10.13.201.115:8080 (ver .env.example). El puerto
# 5432 de iieg-db-etl, en cambio, no responde directo, así que se reenvía a
# localhost reutilizando el host iieg-db-etl de ~/.ssh/config.
#
# ADVERTENCIA CONOCIDA (2026-08-18): el sshd de iieg-db-etl rechaza el reenvío
# de puertos ("administratively prohibited") — política de AllowTcpForwarding/
# PermitOpen del lado del servidor, no un problema de este script. Hasta que un
# administrador de ese host habilite el reenvío para esta llave/usuario, el
# túnel fallará rápido con un mensaje explícito en vez de colgarse en silencio.
#
# Uso:
#   ./scripts/tunel-produccion.sh
set -euo pipefail

PG_LOCAL_PORT="${PG_TUNNEL_LOCAL_PORT:-15432}"
PG_REMOTE_PORT="${PG_TUNNEL_REMOTE_PORT:-5432}"

log=""
pid=""
cleanup() {
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    [[ -n "$log" ]] && rm -f "$log" || true
}
trap cleanup EXIT INT TERM

log="$(mktemp)"
echo "[tunel] postgres: localhost:$PG_LOCAL_PORT -> iieg-db-etl:$PG_REMOTE_PORT" >&2
ssh -N -L "${PG_LOCAL_PORT}:localhost:${PG_REMOTE_PORT}" iieg-db-etl >"$log" 2>&1 &
pid="$!"

rechazado() {
    grep -qi "administratively prohibited" "$log" 2>/dev/null
}

aviso_rechazo() {
    echo "[tunel] postgres: el servidor rechazó el reenvío de puertos" >&2
    echo "[tunel] postgres: revisa la política AllowTcpForwarding/PermitOpen del sshd remoto" >&2
}

# El listener local acepta la conexión TCP en cuanto ssh arranca, aunque el
# servidor remoto rechace el reenvío del canal — por eso además se revisa el
# log de ssh, no solo el socket local.
for _ in $(seq 1 20); do
    if rechazado; then
        aviso_rechazo
        exit 1
    fi
    if (exec 3<>"/dev/tcp/localhost/${PG_LOCAL_PORT}") 2>/dev/null; then
        exec 3>&- 3<&-
        # Se necesita una sonda que realmente envíe datos para que ssh intente
        # abrir el canal remoto y así se dispare (o no) el rechazo del servidor.
        echo | nc -w2 localhost "$PG_LOCAL_PORT" >/dev/null 2>&1 || true
        sleep 1
        if rechazado; then
            aviso_rechazo
            exit 1
        fi
        echo "[tunel] postgres listo en localhost:$PG_LOCAL_PORT"
        echo "[tunel] presiona Ctrl+C para cerrarlo."
        wait
        exit 0
    fi
    sleep 0.5
done

echo "[tunel] postgres no respondió en localhost:$PG_LOCAL_PORT tras 10s" >&2
exit 1
