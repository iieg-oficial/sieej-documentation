# sieej-documentation

Landing page de documentación del **SIEEJ** (Sistema de Información Estratégica del Estado de
Jalisco, IIEG): qué es el sistema, catálogo de sus pipelines ETL en producción, numeralia con
cross check Airflow ↔ base de datos, y estructura de sus vistas materializadas.

## Arquitectura

Sitio **Astro en modo servidor** que consulta la API de mariachi en cada visita, y un
**sincronizador** que alimenta a mariachi en ciclos (decisión original en
[docs/arquitectura.md](docs/arquitectura.md); el cambio a mariachi, en el frente 18 de tamal-rojo):

```
Airflow (API REST) ──┐                                  ┌─> mariachi (schema sieej_documentacion)
PostgreSQL (RO) ─────┼─> builder: datalayer (Python) ───┤        ▲ edición en el admin
README de ETL-SIEEJ ─┘          │ data/*.json            │        │
                                ▼                        └─> web: Astro SSR (Node, :8080)
                          volumen `datos` ──────────────────────▲ respaldo si mariachi no responde
```

- **`datalayer/`** — paquete Python que consulta Airflow y PostgreSQL (**solo lectura**), lee el
  README de cada pipeline de un clon superficial de ETL-SIEEJ (solo `core/pipelines`) y detecta
  pipelines por BD, README, DAG o carpeta. Escribe `data/*.json` y una página por pipeline en
  `data/pipelines/`, y en cada ciclo envía todo a mariachi (`PUT /api/public/sieej-documentacion/sync`,
  llave de servicio). Si la BD o los README caen, conserva los últimos datos válidos; si cae
  Airflow, hereda el último estado de los DAG. Nunca rompe el ciclo.
- **`web/`** — Astro con `@astrojs/node`. Las páginas `/pipelines/<nombre>/` salen de la API pública
  de mariachi, con caché por token de versión; si mariachi no responde, de lo último bueno y luego
  de `data/`. Registra cada visita en la telemetría de mariachi desde el servidor. Las URL antiguas
  `/docs/<nombre>.html` redirigen con 301.
- **`builder/`** — imagen Python que corre el datalayer cada `REBUILD_INTERVAL_SECONDS` (diario por
  defecto). Ya no compila el sitio.
- La BD de producción **nunca** se expone al navegador.

## Arranque con Docker (recomendado)

```bash
make up       # desarrollo: crea .env.development desde .env.example y levanta builder + web
make deploy   # producción: git pull, build, y levanta con .env.production
make help     # el resto de los comandos
```

Compose se divide en `compose.yaml` (base) más `compose.dev.yaml` o `compose.prod.yaml`, siempre
con `-f` explícito; el Makefile arma la invocación. Los proyectos son `sieej-documentation-dev` y
`sieej-documentation`. Todas las variables vienen del archivo de entorno y el compose falla si falta
una; las credenciales y la URL de ETL-SIEEJ pueden ir vacías y el sitio levanta en modo degradado.

| Comando | Qué hace |
|---|---|
| `make up` | Levanta desarrollo sin reconstruir; el sitio queda en `WEB_BIND_ADDR:WEB_PORT` |
| `make deploy` | Actualiza el repo, reconstruye las imágenes y recrea producción |
| `make sync` | Corre un ciclo del sincronizador ahora, sin esperar al siguiente |
| `make mariachi-key` | Genera la clave del sincronizador y muestra la huella para mariachi |
| `make test` | Tests del datalayer en `.venv` (lo crea si falta) |
| `make logs` / `make status` / `make shell` | Diagnóstico del entorno activo |
| `make down` / `make clean` | Detiene, o detiene y borra volúmenes (pide confirmación) |

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
.venv/bin/python -m sieej_datalayer        # regenera data/*.json (lee .env.development)

# Sitio (Node >= 20)
cd web && npm install
npm run dev
npm run build && node dist/server/entry.mjs  # servidor de producción (DATA_DIR, MARIACHI_URL)
```

## Estructura del repositorio

```
├── compose.yaml          # builder + web; overlays compose.dev.yaml y compose.prod.yaml
├── Makefile, make/       # make up / make deploy y comandos del repo
├── .env.example          # plantilla de desarrollo; .env.production.example la de producción
├── web/                  # Astro SSR + Dockerfile (node)
├── datalayer/            # paquete Python sieej-datalayer + tests
├── builder/              # imagen del sincronizador (Python)
├── data/                 # JSON generados (contrato de datos del sitio)
├── docs/                 # arquitectura, tablero de tareas, convención de commits
└── .claude/agents/       # definición de los agentes del proyecto
```

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md): GitHub flow con `main` protegida, una tarea = una rama =
una PR (tablero en [docs/tasks.md](docs/tasks.md)), Conventional Commits y pre-commit con
detección de secretos. Ninguna credencial entra al repositorio: todo por variables de entorno.
