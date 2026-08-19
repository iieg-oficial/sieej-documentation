#!/usr/bin/env bash
# Abre túneles SSH locales hacia la BD de producción y la API de Airflow.
#
# Los puertos de aplicación (Postgres 5432, API de Airflow 8080) no son
# alcanzables directo por IP desde fuera de la red del IIEG; solo el puerto
# SSH de cada host lo es. Este script reenvía ambos puertos a localhost,
# reutilizando los hosts ya definidos en ~/.ssh/config (iieg-db-etl,
# iieg-airflow). Con el túnel activo, sieej_datalayer se apunta a
# localhost:<puerto> vía PG_HOST/AIRFLOW_BASE_URL (ver .env.example).
#
# ADVERTENCIA CONOCIDA (2026-08-18): el sshd de iieg-db-etl rechaza el
# reenvío de puertos ("administratively prohibited") — política de
# AllowTcpForwarding/PermitOpen del lado del servidor, no un problema de
# este script ni de la VPN. El túnel a iieg-airflow sí funciona. Hasta que
# un administrador de iieg-db-etl habilite el reenvío para esta llave/
# usuario, usar --airflow-only; el intento de túnel a Postgres fallará
# rápido con un mensaje explícito en vez de colgarse en silencio.
#
# Uso:
#   ./scripts/tunel-produccion.sh            # abre ambos túneles (foreground)
#   ./scripts/tunel-produccion.sh --pg-only  # solo Postgres
#   ./scripts/tunel-produccion.sh --airflow-only
set -euo pipefail

PG_LOCAL_PORT="${PG_TUNNEL_LOCAL_PORT:-15432}"
PG_REMOTE_PORT="${PG_TUNNEL_REMOTE_PORT:-5432}"
AIRFLOW_LOCAL_PORT="${AIRFLOW_TUNNEL_LOCAL_PORT:-18080}"
AIRFLOW_REMOTE_PORT="${AIRFLOW_TUNNEL_REMOTE_PORT:-8080}"

modo="${1:-}"

pids=()
logs=()
cleanup() {
    for pid in "${pids[@]:-}"; do
        kill "$pid" 2>/dev/null || true
    done
    for log in "${logs[@]:-}"; do
        rm -f "$log"
    done
}
trap cleanup EXIT INT TERM

abrir_tunel() {
    local nombre="$1" host="$2" local_port="$3" remote_port="$4"
    local log
    log="$(mktemp)"
    # El mensaje de estado va a stderr: stdout se reserva para la ruta del
    # log, que el llamador captura con `pg_log="$(abrir_tunel ...)"`.
    echo "[tunel] $nombre: localhost:$local_port -> $host:$remote_port" >&2
    ssh -N -L "${local_port}:localhost:${remote_port}" "$host" >"$log" 2>&1 &
    pids+=("$!")
    logs+=("$log")
    echo "$log"
}

esperar_puerto() {
    # El listener local acepta la conexión TCP en cuanto ssh arranca, aunque
    # el servidor remoto rechace el reenvío del canal ("administratively
    # prohibited") — por eso además se revisa el log de ssh, no solo el
    # socket local.
    local nombre="$1" puerto="$2" log="$3"
    for _ in $(seq 1 20); do
        if grep -qi "administratively prohibited" "$log" 2>/dev/null; then
            echo "[tunel] $nombre: el servidor rechazó el reenvío de puertos" >&2
            echo "[tunel] $nombre: revisa la política AllowTcpForwarding/PermitOpen del sshd remoto" >&2
            return 1
        fi
        if (exec 3<>"/dev/tcp/localhost/${puerto}") 2>/dev/null; then
            exec 3>&- 3<&-
            # El listener local acepta el TCP de inmediato; se necesita una
            # sonda que realmente envíe datos para que ssh intente abrir el
            # canal remoto y así se dispare (o no) el rechazo del servidor.
            echo | nc -w2 localhost "$puerto" >/dev/null 2>&1 || true
            sleep 1
            if grep -qi "administratively prohibited" "$log" 2>/dev/null; then
                echo "[tunel] $nombre: el servidor rechazó el reenvío de puertos" >&2
                echo "[tunel] $nombre: revisa la política AllowTcpForwarding/PermitOpen del sshd remoto" >&2
                return 1
            fi
            echo "[tunel] $nombre listo en localhost:$puerto"
            return 0
        fi
        sleep 0.5
    done
    echo "[tunel] $nombre no respondió en localhost:$puerto tras 10s" >&2
    return 1
}

algun_fallo=0

if [[ "$modo" != "--airflow-only" ]]; then
    pg_log="$(abrir_tunel "postgres" "iieg-db-etl" "$PG_LOCAL_PORT" "$PG_REMOTE_PORT")"
fi
if [[ "$modo" != "--pg-only" ]]; then
    airflow_log="$(abrir_tunel "airflow" "iieg-airflow" "$AIRFLOW_LOCAL_PORT" "$AIRFLOW_REMOTE_PORT")"
fi

if [[ "$modo" != "--airflow-only" ]]; then
    esperar_puerto "postgres" "$PG_LOCAL_PORT" "$pg_log" || algun_fallo=1
fi
if [[ "$modo" != "--pg-only" ]]; then
    esperar_puerto "airflow" "$AIRFLOW_LOCAL_PORT" "$airflow_log" || algun_fallo=1
fi

if [[ "$algun_fallo" -eq 1 ]]; then
    echo "[tunel] al menos un túnel no quedó disponible; revisa los mensajes arriba." >&2
fi
echo "[tunel] presiona Ctrl+C para cerrar los túneles que sí quedaron activos."
wait
