# sieej-documentation

Landing page de documentación del **SIEEJ** (Sistema de Información Estratégica del Estado de
Jalisco, IIEG): qué es el sistema, catálogo de sus pipelines ETL en producción, numeralia con
cross check Airflow ↔ base de datos, y estructura de sus vistas materializadas.

## Arquitectura

Sitio **estático (Astro)** con **capa de datos en build time** y reconstrucción periódica
(decisión documentada en [docs/arquitectura.md](docs/arquitectura.md)):

```
Airflow (API REST) ─┐                      ┌─> web  (nginx no-root, :8080)
                    ├─> datalayer (Python) ─> data/*.json ─> astro build ─> volumen `sitio`
PostgreSQL (RO) ────┘        ▲                                    ▲
HTML de pipelines ───────────┴── builder (reconstrucción periódica) ┘
```

- **`datalayer/`** — paquete Python que consulta Airflow y PostgreSQL (**solo lectura**), cruza
  ambas fuentes con la documentación estática y genera `data/*.json`. Si una fuente cae, conserva
  los últimos datos válidos marcados `datos_obsoletos`; nunca rompe el build.
- **`web/`** — sitio Astro. Los HTML de documentación de pipelines (generados fuera de este
  repositorio) se copian tal cual a `public/docs/` en cada build: un pipeline nuevo aparece en la
  landing con solo reconstruir, sin cambios de código.
- **`builder/`** — contenedor que regenera datos y sitio cada `REBUILD_INTERVAL_SECONDS`
  (diario por defecto) hacia el volumen que sirve nginx.
- La BD de producción **nunca** se expone al navegador: el cliente solo recibe JSON/HTML estático.

## Arranque con Docker (recomendado)

```bash
cp .env.example .env   # completa credenciales y rutas reales
docker compose up -d   # levanta builder + web con healthchecks
```

El sitio queda en `http://localhost:8080` (configurable con `WEB_PORT`). Sin `.env`, el sistema
levanta igualmente en modo degradado (sin fuentes vivas ni documentación montada).

### Acceso de red que necesitan los contenedores

| Destino | Puerto | Uso |
|---|---|---|
| Servidor PostgreSQL de producción (`PG_HOST`) | 5432 | Introspección de solo lectura |
| API REST de Airflow (`AIRFLOW_BASE_URL`) | 8080/https | DAGs y corridas, solo GET |

Ambos son **servicios externos existentes**: no se levantan en este Compose. El usuario de BD y
el de Airflow deben ser de **solo lectura**; además toda conexión a PostgreSQL se abre con
`default_transaction_read_only=on`.

### Acceso vía túnel SSH (fuera de la red interna del IIEG)

Ninguno de los dos puertos de arriba es alcanzable directo por IP desde fuera de la red del
IIEG — solo el puerto SSH de cada host lo es. Con VPN activa y los hosts `iieg-db-etl` /
`iieg-airflow` definidos en `~/.ssh/config`, abre el túnel antes de correr `sieej_datalayer` o
`docker compose up` con fuentes vivas:

```bash
./scripts/tunel-produccion.sh   # ver scripts/README.md para detalles y estado conocido
```

Con el túnel activo, `.env` apunta a `localhost` + los puertos reenviados (ver
`.env.example`). **Estado al 2026-08-18**: el túnel a Airflow funciona; el túnel a Postgres es
rechazado por el `sshd` de `iieg-db-etl` (política `AllowTcpForwarding`/`PermitOpen` del
servidor) — pendiente de que un administrador de ese host lo habilite.

## Desarrollo local

```bash
# Capa de datos (Python >= 3.10)
python3 -m venv .venv && .venv/bin/pip install -e "datalayer[dev]"
.venv/bin/pytest datalayer                 # tests
.venv/bin/python -m sieej_datalayer        # regenera data/*.json (lee .env)

# Sitio (Node >= 20)
cd web && npm install
DOCS_HTML_DIR=/ruta/a/html-documents npm run dev
npm run build                              # build de producción
```

## Estructura del repositorio

```
├── docker-compose.yml    # web + builder (+ redis como perfil opcional `cache`)
├── .env.example          # todas las variables documentadas; credenciales solo por .env
├── web/                  # Astro + Dockerfile (node → nginx-unprivileged)
├── datalayer/            # paquete Python sieej-datalayer + tests
├── builder/              # imagen de reconstrucción periódica
├── data/                 # JSON generados (contrato de datos del sitio)
├── docs/                 # arquitectura, tablero de tareas, convención de commits
└── .claude/agents/       # definición de los agentes del proyecto
```

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md): GitHub flow con `main` protegida, una tarea = una rama =
una PR (tablero en [docs/tasks.md](docs/tasks.md)), Conventional Commits y pre-commit con
detección de secretos. Ninguna credencial entra al repositorio: todo por variables de entorno.
