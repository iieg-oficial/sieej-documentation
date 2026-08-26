# Runbook — cruce real contra Airflow y BD de producción (T5.1.3)

> Este documento existe para dejar listos los pasos exactos y no perder contexto entre
> sesiones. La tarea está **bloqueada** hasta resolver los tres puntos de la sección
> "Bloqueadores" — no ejecutar hasta entonces.

## Bloqueadores (2026-08-18)

1. **Túnel SSH a Postgres rechazado por el servidor** (T5.1.1). El `sshd` de `iieg-db-etl`
   responde `administratively prohibited` al reenvío de puertos — política
   `AllowTcpForwarding`/`PermitOpen` del lado del servidor. Requiere que un administrador de
   ese host lo habilite para la llave/usuario en uso, o una ruta de acceso alternativa.
2. **Credenciales de solo lectura**, aún no recibidas:
   - Airflow: usuario/contraseña de la API REST (`AIRFLOW_USERNAME`/`AIRFLOW_PASSWORD`).
   - PostgreSQL: usuario/contraseña de solo lectura (`PG_USER`/`PG_PASSWORD`); **no reutilizar**
     la cuenta admin existente (la cuenta admin usada para el volcado puntual de `etl-views/`).
3. **El Airflow de producción es 3.1.1**, que expone `/api/v2` — confirmado el 2026-08-26
   contra el servidor real: `/api/v2/version` responde `{"version":"3.1.1"}` y `/api/v1/dags`
   da 404. `datalayer/sieej_datalayer/airflow_client.py` apunta hoy a `/api/v1` con HTTP Basic;
   necesita migrarse antes de que `consultar_airflow()` funcione contra producción. También
   cambia la autenticación: `/api/v2/dags` responde `401 Not authenticated` y el endpoint
   `POST /auth/token` existe, así que el flujo es **JWT** (`/auth/token` → `Authorization:
   Bearer`), no HTTP Basic.

## Pasos una vez desbloqueado

```bash
# 1. Abrir el túnel de Postgres (Airflow NO usa túnel: responde directo por IP)
./scripts/tunel-produccion.sh

# 2. Completar .env con las credenciales reales
cp .env.example .env
#   AIRFLOW_BASE_URL=http://10.13.201.115:8080   # directo, sin túnel
#   AIRFLOW_USERNAME=<usuario de solo lectura>
#   AIRFLOW_PASSWORD=<contraseña>
#   PG_HOST=localhost
#   PG_PORT=15432
#   PG_USER=<usuario de solo lectura>
#   PG_PASSWORD=<contraseña>

# 3. Regenerar los JSON contra fuentes vivas
.venv/bin/python -m sieej_datalayer

# 4. Verificar el resultado
python3 -c "
import json
inv = json.load(open('data/inventario.json'))
print('verificado_contra_produccion:', inv['resumen']['verificado_contra_produccion'])
print('resumen:', inv['resumen'])
print('cross_check:', inv['cross_check'])
"
```

## Criterio de terminado

- Los 3 JSON (`inventario.json`, `numeralia.json`, `vistas.json`) se regeneran desde fuentes
  vivas sin degradar (`fuentes.airflow.estado` y `fuentes.bd.estado` en `ok`).
- `resumen.verificado_contra_produccion` queda en `true`.
- Cualquier discrepancia real entre Airflow/BD/documentación estática queda reflejada en
  `cross_check`, no oculta.
- Commit de los 3 JSON resultantes.

## Al completar

Borrar este runbook (su contenido pasa a ser historia de commits) y actualizar T5.1.3 en
`docs/tasks.md` a `[x]`.
