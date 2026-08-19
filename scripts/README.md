# scripts/

## `tunel-produccion.sh`

Abre túneles SSH locales hacia la BD de producción (`iieg-db-etl`) y la API de Airflow
(`iieg-airflow`), reutilizando los hosts ya definidos en `~/.ssh/config`. Necesario porque los
puertos de aplicación (Postgres `5432`, API de Airflow `8080`) no son alcanzables directo por
IP desde fuera de la red del IIEG — solo el puerto SSH de cada host lo es.

```bash
./scripts/tunel-produccion.sh              # ambos túneles
./scripts/tunel-produccion.sh --pg-only    # solo Postgres
./scripts/tunel-produccion.sh --airflow-only
```

Con el túnel activo, apunta `sieej_datalayer` a `localhost:<puerto>` vía
`PG_HOST`/`AIRFLOW_BASE_URL` en `.env` (puertos por defecto: `15432` para Postgres, `18080`
para Airflow; configurables con `PG_TUNNEL_LOCAL_PORT`/`AIRFLOW_TUNNEL_LOCAL_PORT`).

### Estado conocido (2026-08-18)

- **Airflow**: el túnel funciona — tráfico HTTP real confirmado contra `localhost:18080`.
- **Postgres**: el `sshd` de `iieg-db-etl` rechaza el reenvío de puertos
  (`administratively prohibited`) — política `AllowTcpForwarding`/`PermitOpen` del lado del
  servidor. El script detecta este rechazo y falla rápido con un mensaje explícito en vez de
  colgarse. Requiere que un administrador de `iieg-db-etl` habilite el reenvío para la llave/
  usuario usados, o una ruta de acceso alternativa a Postgres.
