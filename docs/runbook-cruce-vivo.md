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
3. **El Airflow de producción es v3**, que expone `/api/v2` — confirmado con un 404 real vía
   túnel contra `/api/v1/dags`. `datalayer/sieej_datalayer/airflow_client.py` apunta hoy a
   `/api/v1`; necesita migrarse antes de que `consultar_airflow()` funcione contra producción.
   Los endpoints v2 relevantes (a verificar contra la documentación de Airflow 3): listar DAGs
   y corridas recientes por DAG. El esquema de autenticación también puede diferir (Airflow 3
   usa JWT por defecto en vez de HTTP Basic) — confirmar contra el servidor real antes de
   escribir el cliente nuevo.

## Pasos una vez desbloqueado

```bash
# 1. Abrir los túneles (ambos deben responder)
./scripts/tunel-produccion.sh

# 2. Completar .env con las credenciales reales, apuntando a los túneles
cp .env.example .env
#   AIRFLOW_BASE_URL=http://localhost:18080
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
