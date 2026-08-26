# scripts/

## `tunel-produccion.sh`

Abre un túnel SSH local hacia la BD de producción (`postgis_db` en `iieg-db-etl`),
reutilizando el host ya definido en `~/.ssh/config`. Necesario porque el puerto `5432` de ese
host no es alcanzable directo por IP desde fuera de la red del IIEG.

```bash
./scripts/tunel-produccion.sh
```

Con el túnel activo, apunta `sieej_datalayer` a `localhost` vía `PG_HOST`/`PG_PORT` en `.env`
(puerto local por defecto: `15432`, configurable con `PG_TUNNEL_LOCAL_PORT`).

**Airflow no usa este script.** Su API sí responde directo por IP
(`http://10.13.201.115:8080`), así que `AIRFLOW_BASE_URL` apunta ahí sin intermediarios — ver
`.env.example`.

### Estado conocido (2026-08-26)

- **Airflow**: alcanzable directo por HTTP, sin túnel. Verificado contra
  `http://10.13.201.115:8080/api/v2/version` → Airflow **3.1.1**.
- **Postgres**: el `sshd` de `iieg-db-etl` rechaza el reenvío de puertos
  (`administratively prohibited`) — política `AllowTcpForwarding`/`PermitOpen` del lado del
  servidor. El script detecta este rechazo y falla rápido con un mensaje explícito en vez de
  colgarse. Requiere que un administrador de `iieg-db-etl` habilite el reenvío para la llave/
  usuario usados, o una ruta de acceso alternativa.
- Desde la red donde se probó el 2026-08-26, además, el puerto SSH de `iieg-db-etl`
  (`49222`) no responde: el túnel no puede siquiera intentarse sin VPN.
