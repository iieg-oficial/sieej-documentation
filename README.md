# sieej-documentation

Landing page de documentación del **SIEEJ** (Sistema de Información Estratégica del Estado de
Jalisco, IIEG): qué es el sistema, catálogo de sus pipelines ETL en producción, numeralia con
cross check Airflow ↔ base de datos, y estructura de sus vistas materializadas.

## Arquitectura

Sitio **estático (Astro)** con **capa de datos en build time** y reconstrucción periódica
(decisión documentada en [docs/arquitectura.md](docs/arquitectura.md)):

```
Airflow (API REST) ──┐                      ┌─> web  (nginx no-root, :8080)
PostgreSQL (RO) ─────┼─> datalayer (Python) ─> data/ ─> astro build ─> volumen `sitio`
README de ETL-SIEEJ ─┘        ▲                                  ▲
                              └── builder (reconstrucción periódica) ┘
```

- **`datalayer/`** — paquete Python que consulta Airflow y PostgreSQL (**solo lectura**), lee el
  README de cada pipeline de un clon superficial de ETL-SIEEJ (solo `core/pipelines`) y genera
  `data/*.json` más una página por pipeline en `data/pipelines/`: texto, tablas con filas,
  vistas con columnas y las llaves foráneas del diagrama entidad-relación. Si la BD o los README
  caen, conserva los últimos datos válidos marcados `datos_obsoletos`; si cae Airflow, hereda el
  último estado de los DAG. Nunca rompe el build.
- **`web/`** — sitio Astro. Cada pipeline tiene su página `/pipelines/<nombre>/` con el diseño del
  sitio; un pipeline nuevo aparece con solo reconstruir, sin cambios de código. Las URL antiguas
  `/docs/<nombre>.html` redirigen con 301.
- **`builder/`** — contenedor que regenera datos y sitio cada `REBUILD_INTERVAL_SECONDS`
  (diario por defecto) hacia el volumen que sirve nginx.
- La BD de producción **nunca** se expone al navegador: el cliente solo recibe JSON/HTML estático.

## Arranque con Docker (recomendado)

```bash
cp .env.example .env   # completa credenciales y rutas reales
docker compose up -d   # levanta builder + web con healthchecks
```

El sitio queda en `http://localhost:8080` (configurable con `WEB_PORT`). Sin `.env`, el sistema
levanta igualmente en modo degradado (sin fuentes vivas ni README de ETL-SIEEJ).

### Acceso de red que necesitan los contenedores

| Destino | Puerto | Uso |
|---|---|---|
| Servidor PostgreSQL de producción (`PG_HOST`) | 5432 | Introspección de solo lectura |
| API REST de Airflow (`AIRFLOW_BASE_URL`) | 8080/https | DAGs y corridas, solo GET |
| GitHub (`ETL_REPO_URL`) | 443 | Clon superficial de ETL-SIEEJ, solo `core/pipelines` |

Ambos son **servicios externos existentes**: no se levantan en este Compose. El usuario de BD y
el de Airflow deben ser de **solo lectura**; además toda conexión a PostgreSQL se abre con
`default_transaction_read_only=on`.

La API de Airflow es la **v2 de Airflow 3**, que autentica con **JWT**: `AIRFLOW_USERNAME` y
`AIRFLOW_PASSWORD` se cambian por un token en `POST /auth/token` (`AIRFLOW_TOKEN_PATH`) y este
viaja como `Authorization: Bearer` en cada GET. Si el token ya viene emitido, ponlo en
`AIRFLOW_TOKEN` y el intercambio se omite.

## Desarrollo local

```bash
# Capa de datos (Python >= 3.10)
python3 -m venv .venv && .venv/bin/pip install -e "datalayer[dev]"
.venv/bin/pytest datalayer                 # tests
.venv/bin/python -m sieej_datalayer        # regenera data/*.json (lee .env)

# Sitio (Node >= 20)
cd web && npm install
npm run dev
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
