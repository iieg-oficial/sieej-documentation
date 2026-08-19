# Contexto de sesión — Inventario vivo (SSH/VPN) hasta 2026-08-19

> Complementa a `docs/session-context/contexto-sesion-2026-08.md` (contexto general del
> proyecto hasta el 2026-08-17). Este archivo cubre solo lo trabajado en esta sesión: el
> primer intento real de conectar `sieej_datalayer` contra Airflow y PostgreSQL de producción
> ahora que hay VPN activa. Describe el trabajo de **cada rama creada**, no repite un archivo
> por rama.

## Punto de partida

Al arrancar la sesión, el usuario confirmó que ya tenía **VPN activa** y las credenciales SSH
de `iieg-db-etl` / `iieg-airflow` en `~/.ssh/config` (mismos hosts usados en sesiones previas,
antes inalcanzables). Pidió: crear las tareas atómicas de T5.1 en GitHub (issues + rama + PR)
antes de continuar con la implementación.

## Qué se hizo, rama por rama

### `docs/desglose-t5.1` (mergeada — PR #31)

Primer paso: comprobé la conectividad real antes de diseñar las tareas. Resultado: SSH sí
llega a ambos hosts, pero los puertos de aplicación (Postgres `5432`, API de Airflow `8080`)
**no** son alcanzables directo por IP — solo el puerto SSH. Esto definió el enfoque: acceso vía
**túnel SSH**, no conexión directa.

Con eso, reemplacé la tarea única `T5.1` en `docs/tasks.md` por una nueva **Fase 5** con cuatro
subtareas atómicas (T5.1.1–T5.1.4), cada una con su propia rama/PR prevista. Esta rama se
mergeó primero para que el tablero reflejara el desglose antes de abrir las demás ramas.

### Issues de GitHub creados (sin rama propia)

`gh issue create` para las 4 subtareas, cada uno referenciando su ID de tablero:

- **#32** — Túneles SSH hacia Postgres y Airflow (T5.1.1)
- **#33** — Cableado de `.env`/README hacia los túneles (T5.1.2)
- **#34** — Ejecutar el cruce real y regenerar `data/*.json` (T5.1.3)
- **#35** — Verificación end-to-end del cruce en el sitio (T5.1.4)

### `feature/datalayer-tunel-ssh` (PR #36, **borrador**, sin mergear)

Implementé `scripts/tunel-produccion.sh`: abre reenvíos SSH locales (`ssh -N -L`) hacia
`postgis_db` (`iieg-db-etl:5432`) y la API de Airflow (`iieg-airflow:8080`), reutilizando los
hosts de `~/.ssh/config`. Lo probé contra los servidores reales (no simulado):

- **Airflow: funciona.** Confirmado con tráfico HTTP real (`curl` contra `localhost:18080`
  devuelve 200). De paso se descubrió que el Airflow de producción es **v3**, que expone
  `/api/v2` (el `/api/v1` que consulta la respuesta de error confirma que fue retirado).
- **Postgres: rechazado por el servidor.** El `sshd` de `iieg-db-etl` responde
  `administratively prohibited` al intentar abrir el canal de reenvío — es una política
  `AllowTcpForwarding`/`PermitOpen` del lado del servidor, no un problema de este script ni de
  la VPN. Confirmado probando varias formas del destino (`localhost`, `127.0.0.1`, puertos
  distintos): siempre falla igual, así que es un bloqueo total, no una particularidad de
  nombre de host.
- El script detecta este rechazo revisando el log de `ssh` (busca la cadena
  `administratively prohibited`) tras forzar una sonda real con `nc`, y falla rápido con un
  mensaje explícito en vez de colgarse en silencio esperando un puerto que nunca respondía por
  el canal real (el listener local siempre acepta el TCP, aunque el reenvío al destino final
  esté bloqueado — hubo que enviar datos de verdad a través del socket para disparar el
  intento de apertura de canal y detectar el rechazo).
- `docs/tasks.md`: T5.1.1 actualizada con el hallazgo (Airflow cumple el CT, Postgres no).

**Por qué sigue como borrador**: el criterio de terminado original pedía que ambos túneles
respondieran; solo uno lo hace. Queda documentado y abierto hasta que un administrador de
`iieg-db-etl` habilite el reenvío de puertos para esta llave/usuario, o aparezca una ruta de
acceso alternativa a Postgres.

### `chore/datalayer-tunel-config` (PR #37, **borrador**, sin mergear)

Cableé `.env.example` y `README.md` para documentar los endpoints del túnel
(`AIRFLOW_BASE_URL=http://localhost:18080`, `PG_HOST=localhost`/`PG_PORT=15432`). Verifiqué
que el cableado es correcto abriendo el túnel de Airflow manualmente y corriendo
`consultar_airflow()` del datalayer contra él: la conexión llegó de verdad al servidor real
(la respuesta fue un 404 en `/api/v1/dags`, no un error de conectividad), lo que también
confirmó de forma independiente el hallazgo de Airflow v3 de la rama anterior. El lado de
Postgres quedó documentado pero sin poder verificarse, porque depende de que T5.1.1 desbloquee
su túnel.

### `feature/datalayer-cruce-vivo` (PR #38, **borrador**, sin mergear)

No hay trabajo ejecutable todavía — esta tarea depende de tres cosas que aún no existen:
credenciales de solo lectura reales (Airflow y PostgreSQL), el desbloqueo del túnel de
Postgres, y la migración de `datalayer/sieej_datalayer/airflow_client.py` de `/api/v1` a
`/api/v2` (Airflow 3). En vez de dejar la tarea sin rastro, escribí
`docs/runbook-cruce-vivo.md`: un runbook con los comandos exactos a correr en cuanto se
resuelvan los tres bloqueadores, para no perder el contexto entre sesiones.

### `chore/verificacion-cruce-vivo` (PR #39, **borrador**, sin mergear)

Igual que la anterior: sin trabajo ejecutable (depende por completo de T5.1.3). Escribí
`docs/runbook-verificacion-cruce-vivo.md` con los pasos para reconstruir el stack y verificar
visualmente que el catálogo, la numeralia y las vistas reflejan datos vivos una vez que existan.

## Estado consolidado al cierre de la sesión

| Rama | PR | Estado |
|---|---|---|
| `docs/desglose-t5.1` | #31 | Mergeada, rama borrada |
| `feature/datalayer-tunel-ssh` | #36 | Borrador — Airflow listo, Postgres bloqueado |
| `chore/datalayer-tunel-config` | #37 | Borrador — Airflow listo, Postgres pendiente |
| `feature/datalayer-cruce-vivo` | #38 | Borrador — solo runbook, bloqueada |
| `chore/verificacion-cruce-vivo` | #39 | Borrador — solo runbook, bloqueada |

`main` está al día con todo lo mergeable (el desglose del tablero). Los tres bloqueadores
reales que impiden avanzar T5.1 completa:

1. **Postgres**: un administrador de `iieg-db-etl` debe habilitar `AllowTcpForwarding`/
   `PermitOpen` en el `sshd` para la llave/usuario en uso — o aparecer una ruta alternativa.
2. **Credenciales de solo lectura** de Airflow y PostgreSQL — aún no entregadas. Para Postgres,
   no reutilizar la cuenta admin existente (cuenta admin usada en el volcado puntual de `etl-views/`).
3. **Migración del cliente de Airflow** en `datalayer/sieej_datalayer/airflow_client.py`, de
   `/api/v1` (retirado) a `/api/v2` (Airflow 3). Falta confirmar contra el servidor real si
   también cambió el esquema de autenticación (Airflow 3 suele usar JWT en vez de HTTP Basic).

## Impacto funcional real: ninguno todavía

Vale la pena decirlo sin rodeos: **el sitio que corre en `localhost:18081` sigue exactamente
igual que antes de esta sesión.** Nada de lo producido aquí cambió lo que el usuario final ve
o lo que el sistema hace en producción. Desglosado:

- Lo único que es **código ejecutable** en esta sesión es `scripts/tunel-produccion.sh`
  (`feature/datalayer-tunel-ssh`, PR #36). Es una herramienta de infraestructura para uso
  manual — no está integrada a `datalayer/`, a `docker-compose.yml` ni al `builder`, así que
  el proceso de reconstrucción automática del sitio no la usa ni se ve afectado por ella.
- Todo lo demás (`.env.example`, `README.md`, `docs/tasks.md`, los dos runbooks, este mismo
  archivo) es **documentación y configuración de referencia**: texto que orienta a un humano,
  no lógica que el sistema ejecute solo.
- Ninguna PR de esta sesión se mergeó a `main`, salvo el desglose del tablero
  (`docs/desglose-t5.1`), que tampoco cambia comportamiento — solo reorganiza tareas.
- El paquete `datalayer/` (Python), el sitio `web/` (Astro) y el `docker-compose.yml` quedan
  **byte por byte igual** que al cierre de la sesión anterior (2026-08-17).

Lo que sí se logró es información nueva y verificada (Airflow alcanzable y es v3; Postgres
bloqueado por política del servidor) que evita repetir ese descubrimiento en la próxima
sesión — pero es conocimiento, no funcionalidad entregada.

## Cómo retomar

1. Resolver el bloqueador de Postgres (fuera del alcance de Claude Code — requiere acción de
   un administrador del servidor) y/o recibir las credenciales de solo lectura.
2. Si se resuelve Postgres: completar y mergear `feature/datalayer-tunel-ssh` (#36) y
   `chore/datalayer-tunel-config` (#37) tal como están, o ampliarlas si el mecanismo cambia.
3. Migrar `airflow_client.py` a `/api/v2` (puede hacerse en paralelo, sin esperar credenciales,
   probando el esquema de la API contra el 404 ya observado — aunque para probar
   autenticación real sí se necesitan las credenciales).
4. Seguir los runbooks de `docs/runbook-cruce-vivo.md` y
   `docs/runbook-verificacion-cruce-vivo.md` en orden.
5. Al completar T5.1.3 y T5.1.4, borrar ambos runbooks (su contenido pasa a ser historia de
   commits) y marcar toda la Fase 5 como `[x]` en `docs/tasks.md`.
