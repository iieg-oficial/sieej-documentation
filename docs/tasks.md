# Tablero de tareas — Landing de documentación del SIEEJ

> Regla: **una tarea = una rama = una PR** (ver [CONTRIBUTING.md](../CONTRIBUTING.md)).
> Estado: `[ ]` pendiente · `[x]` completada. Cada tarea lista su rama, agente asignado,
> dependencias y criterio de terminado (CT).

## Fase 0 — Flujo de desarrollo (agente: git-flujo)

- [x] **T0.1** Bootstrap del flujo de desarrollo — rama `chore/flujo-desarrollo`
  - Incluye: `.gitignore`, agentes en `.claude/agents/`, `docs/arquitectura.md`,
    `data/inventario.json`, `CONTRIBUTING.md`, plantilla de PR, convención de commits,
    este tablero y `.pre-commit-config.yaml`.
  - CT: PR mergeada; `pre-commit run --all-files` pasa; ningún secreto en el diff.
  - Dependencias: ninguna.

## Fase 1 — Capa de datos (agente: datos-backend)

- [x] **T1.1** Esqueleto del paquete `datalayer` — rama `feature/datalayer-base`
  - `pyproject.toml`, `sieej_datalayer/` con configuración por variables de entorno
    (Pydantic Settings) y modelos de datos del contrato (`inventario`, `numeralia`, `vistas`).
  - CT: `pip install -e .` y `pytest` en verde; sin credenciales hardcodeadas.
  - Dependencias: T0.1.
- [x] **T1.2** Cliente de la API REST de Airflow — rama `feature/datalayer-airflow`
  - DAGs (activos/pausados), última corrida y estado, conteos de éxitos/fallos recientes.
  - CT: tests unitarios con respuestas simuladas de la API; manejo de fuente caída.
  - Dependencias: T1.1.
- [x] **T1.3** Introspección de PostgreSQL — rama `feature/datalayer-introspeccion`
  - Bases, vistas/matviews (`pg_matviews`, `pg_views`), columnas y tipos
    (`information_schema.columns`), comentarios (`col_description`), conteos y fechas.
  - CT: tests unitarios con conexión simulada; consultas 100 % de solo lectura.
  - Dependencias: T1.1.
- [x] **T1.4** Cross check + CLI generador de JSON con degradación — rama `feature/datalayer-crosscheck`
  - Cruce Airflow↔BD↔documentación estática; genera `data/*.json`; si una fuente cae,
    reutiliza el último JSON válido y marca `datos_obsoletos`; nunca truena el build.
  - CT: `python -m sieej_datalayer` genera los 3 JSON sin acceso a fuentes vivas
    (modo degradado desde documentación estática); tests del cross check.
  - Dependencias: T1.2, T1.3.

## Fase 2 — Landing Astro (agente: frontend-astro)

- [x] **T2.1** Scaffold de Astro + layout + sistema de diseño — rama `feature/web-scaffold`
  - Proyecto Astro estático en `web/`, layout base, paleta institucional, tipografía,
    navegación, footer, metadatos SEO/OG, es-MX.
  - CT: `npm run build` sin errores ni warnings.
  - Dependencias: T0.1.
- [x] **T2.2** Sección "El SIEEJ" — rama `feature/web-seccion-sieej`
  - Información estratégica estatal, definición, objetivos, qué es un ETL y paradigma
    de desarrollo, **fiel** a `sieej_definicion_caracteristicas_objetivos.md`.
  - CT: contenido cotejado contra el documento fuente; sin contenido inventado.
  - Dependencias: T2.1.
- [x] **T2.3** Copia de HTML de pipelines en build — rama `feature/web-docs-html`
  - Script de build que copia `DOCS_HTML_DIR` → `web/public/docs/` (glob, absorbe archivos
    nuevos sin cambios de código); degrada con aviso si el directorio no está disponible.
  - CT: los 22 HTML + `assets/` accesibles bajo `/docs/` en el build local.
  - Dependencias: T2.1.
- [x] **T2.4** Catálogo de pipelines — rama `feature/web-catalogo`
  - Tarjetas desde `data/inventario.json`: enlace al HTML cuando existe, insignia
    "documentación pendiente" cuando no, marca "posible desactualizado" para HTML sin
    pipeline activo.
  - CT: catálogo refleja el inventario sin listas hardcodeadas.
  - Dependencias: T2.1, T2.3.
- [x] **T2.5** Numeralia con cross check — rama `feature/web-numeralia`
  - Cifras de Airflow y BD desde `data/numeralia.json`; consistencia evidenciada y
    discrepancias marcadas visualmente; aviso de antigüedad si `datos_obsoletos`.
  - CT: renderiza los tres orígenes y sus discrepancias; degrada con gracia.
  - Dependencias: T2.1, T1.4.
- [x] **T2.6** Estructura de vistas materializadas — rama `feature/web-vistas`
  - Navegable por base de datos desde `data/vistas.json`: columnas, tipos, descripciones;
    banderas `solo_en_bd` / `solo_en_docs`.
  - CT: navegación por BD funcional; discrepancias visibles.
  - Dependencias: T2.1, T1.4.

- [x] **T2.7** Homologación de identidad visual con docs/ — rama `feature/web-identidad-visual`
  - Tipografía institucional (Poppins + JetBrains Mono, autoalojadas), logos IIEG/Jalisco en
    hero, header y footer (barra gris pizarra), fondo `#EEF2F3`; inyección de las mismas
    webfonts en los HTML copiados de `docs/` para unificar el tipo de letra.
  - CT: home y docs comparten tipografía y logos; build limpio.
  - Dependencias: T2.1, T2.3.

- [x] **T2.8** Retirar el índice de pipelines de docs/ — rama `update/docs-sin-indice`
  - El catálogo de la landing reemplaza a `docs/index.html`: se excluye de la copia, el
    destino se limpia en cada build (sin arrastrar archivos retirados del origen) y nginx
    redirige `/docs/` → `/#catalogo`.
  - CT: `/docs/index.html` ya no se publica; los 22 documentos siguen accesibles.
  - Dependencias: T2.7.

- [x] **T2.9** Texto curado de definición y objetivos del SIEEJ — rama `update/web-texto-sieej`
  - Las tarjetas «¿Qué es el SIEEJ?» y «Objetivos del SIEEJ» usan el texto de
    `definiciones_sieej_para_landing.md` (definición + objetivo general + 3 objetivos).
  - CT: contenido cotejado contra el archivo curado; build limpio.
  - Dependencias: T2.2.

- [x] **T2.10** Diagrama general del SIEEJ tras los objetivos — rama `update/web-diagrama-sieej`
  - `sistema_informacion_estrategica_estado_jalisco_SIEEJ_0.svg` en tarjeta propia con
    `figure/figcaption`, alt descriptivo y carga diferida.
  - CT: diagrama visible y responsivo tras la tarjeta de objetivos; build limpio.
  - Dependencias: T2.9.

- [x] **T2.11** Sección «Características del SIEEJ» — rama `update/web-caracteristicas-sieej`
  - Tras «Objetivos del SIEEJ»: resúmenes (≤7 líneas) de las explicaciones de ambas figuras
    (fuente: sieej_definicion_caracteristicas_objetivos.md) seguidos de los diagramas
    SIEEJ_0.svg y SIEEJ_1 (servido como WebP optimizado: el SVG fuente pesa 3 MB por PNGs incrustados), este último con la leyenda «Diagrama general del flujo que
    siguen los datos dentro del SIEEJ».
  - CT: sección visible con los dos resúmenes y las dos figuras; build limpio.
  - Dependencias: T2.10.

- [x] **T2.12** Reorden de «Características del SIEEJ» — rama `update/web-orden-caracteristicas`
  - El diagrama general va inmediatamente después del primer párrafo (captación); el
    diagrama de flujo permanece tras el párrafo de tecnologías.
  - CT: orden párrafo→figura→párrafo→figura; build limpio.
  - Dependencias: T2.11.

- [x] **T2.13** Retirar la tarjeta «¿Qué es un flujo ETL?» — rama `update/web-sin-etl`
  - Se elimina la tarjeta de la sección «El SIEEJ»; el resto no cambia.
  - CT: la tarjeta ya no aparece; build limpio.
  - Dependencias: T2.12.

- [x] **T2.14** Texto definitivo de la sección «El SIEEJ» — rama `update/web-texto-mejorado`
  - Todas las tarjetas de la sección usan el texto de `texto_mejorado_para_landing_sieej.md`;
    imágenes y su orden intactos; secciones desde el catálogo sin cambios.
  - CT: contenido cotejado contra el archivo; build limpio.
  - Dependencias: T2.13.

- [x] **T2.15** Quitar negritas de la sección «El SIEEJ» — rama `update/web-sin-negritas`
  - Se retiran todas las negritas del texto, conservando únicamente «Mirador IIEG» en
    «Tecnologías del sistema».
  - CT: una sola negrita restante; build limpio.
  - Dependencias: T2.14.

- [x] **T2.16** Visor ampliado de los diagramas del SIEEJ — rama `feature/web-visor-diagramas`
  - Componente reutilizable (`web/src/components/VisorDiagrama.astro`) que envuelve una figura
    y agrega un botón «Ampliar»; al pulsarlo abre la imagen a tamaño completo en una ventana
    modal (`<dialog>` nativo, sin dependencias externas) sobre un fondo atenuado, con la
    leyenda de la figura y botón de cierre. Se aplica a los dos diagramas de «Características
    del SIEEJ»: el diagrama general del SIEEJ (`SIEEJ_0.svg`) y el diagrama general del flujo
    que siguen los datos dentro del SIEEJ (`SIEEJ_1.webp`).
  - Accesibilidad: botón con nombre accesible por diagrama, cierre con `Esc` y con clic en el
    fondo, foco atrapado dentro del modal y devuelto al botón de origen al cerrar, `alt`
    conservado. Sin JS el sitio sigue siendo legible (la figura se muestra igual, el botón
    solo aparece cuando el script está disponible).
  - CT: los dos diagramas abren y cierran en modal en escritorio y móvil; navegación por
    teclado completa; `npm run build` limpio; sin regresión visual en el resto de la sección.
  - Dependencias: T2.15.

- [x] **T2.17** Zoom y desplazamiento dentro del visor — rama `feature/web-visor-zoom`
  - Dentro del modal, la imagen se puede acercar/alejar y desplazar para leer las etiquetas
    del diagrama de flujo (1670×942), que a ancho de pantalla completo queda ilegible en
    móvil. Controles visibles (`+`, `−`, restablecer) además de rueda/pellizco y arrastre.
  - CT: el texto del diagrama de flujo es legible en un viewport de 375 px; los controles son
    operables por teclado; `npm run build` limpio.
  - Dependencias: T2.16.

## Fase 3 — Infraestructura (agentes: datos-backend + git-flujo)

- [x] **T3.1** Dockerfile de `web` — rama `chore/docker-web`
  - Multi-stage: Node (datos + `astro build`) → nginx sirviendo `dist/`, usuario no-root,
    healthcheck HTTP.
  - CT: `docker build` y contenedor sano sirviendo el sitio.
  - Dependencias: T2.4.
- [x] **T3.2** Servicio `builder` con reconstrucción programada — rama `chore/docker-builder`
  - Imagen Python+Node con supercronic; `REBUILD_CRON` regenera JSON y reconstruye el
    sitio al volumen servido; webhook opcional para disparo desde Airflow.
  - CT: una corrida del builder reconstruye el sitio end-to-end en local.
  - Dependencias: T1.4, T3.1.
- [x] **T3.3** `docker-compose.yml` + `.env.example` + README — rama `chore/compose`
  - Compose raíz con healthchecks y `depends_on` condicionado; `.env.example` completo;
    README con arquitectura, arranque y accesos de red requeridos (BD y Airflow externos).
  - CT: `docker compose up` levanta el sistema completo con healthchecks en verde.
  - Dependencias: T3.1, T3.2.

## Fase 4 — QA (agente: qa-revisor)

- [x] **T4.1** Verificación de criterios de aceptación — sin rama (solo lectura)
  - Build limpio, links a los 22 HTML, sin secretos en código ni historial, accesibilidad,
    fidelidad del contenido, convenciones de git, tablero al día.
  - CT: reporte con hallazgos por severidad; bloqueantes en cero.
  - Dependencias: todas las anteriores.

## Fase 5 — Inventario vivo contra producción (agente: datos-backend)

> VPN y acceso SSH a `iieg-db-etl` / `iieg-airflow` disponibles desde 2026-08-18. Postgres
> (`5432`) y la API de Airflow (`8080`) no son alcanzables directo por IP — solo el puerto SSH
> lo es — así que el acceso pasa por **túneles SSH** reenviados a `localhost`, reutilizando los
> hosts ya definidos en `~/.ssh/config`.

- [ ] **T5.1.1** Túneles SSH hacia Postgres y Airflow — rama `feature/datalayer-tunel-ssh`
  - Script que abre los reenvíos locales hacia `postgis_db` (`iieg-db-etl:5432`) y la API de
    Airflow (`iieg-airflow:8080`), documentado en el README.
  - CT: con el script corriendo, `localhost:<puerto>` responde para ambos túneles.
  - Dependencias: acceso SSH por VPN (ya disponible).
- [ ] **T5.1.2** Cableado de `.env`/README hacia los túneles — rama `chore/datalayer-tunel-config`
  - `.env.example` documenta `PG_HOST`/`AIRFLOW_BASE_URL` apuntando a `localhost` + los puertos
    reenviados; README explica que el túnel de T5.1.1 debe estar activo antes de correr
    `sieej_datalayer` o `docker compose up` con fuentes vivas.
  - CT: con el túnel activo, `python -m sieej_datalayer` intenta conectar a los endpoints
    correctos (verificable aunque aún falten credenciales de aplicación). **Verificado para
    Airflow**: con el túnel abierto, `consultar_airflow()` llega al servidor real (404 por la
    versión de API, no por conectividad — ver hallazgo de Airflow v3 en T5.1.3). El lado de
    Postgres queda documentado pero no verificable hasta que T5.1.1 desbloquee su túnel.
  - Dependencias: T5.1.1 (el lado de Airflow ya se puede cablear; el de Postgres queda pendiente
    del desbloqueo del túnel).
- [ ] **T5.1.3** Ejecutar el cruce real y regenerar `data/*.json` — rama `feature/datalayer-cruce-vivo`
  - Correr `sieej_datalayer` con credenciales de solo lectura reales de Airflow y PostgreSQL;
    verificar clasificación de pipelines, discrepancias y `verificado_contra_produccion: true`.
  - **Hallazgo (2026-08-18):** el Airflow de producción es **v3**, que expone `/api/v2` (el
    `/api/v1` que usa hoy `datalayer/sieej_datalayer/airflow_client.py` fue retirado —
    confirmado con un 404 real contra el servidor vía túnel). El cliente necesita migrarse a
    v2 antes de que esta tarea pueda completarse, además del desbloqueo del túnel de Postgres.
  - CT: los 3 JSON se regeneran desde fuentes vivas sin degradar; commit de los JSON resultantes.
  - Dependencias: T5.1.2 + credenciales de solo lectura de Airflow y PostgreSQL (pendientes) +
    migración del cliente de Airflow a `/api/v2` + desbloqueo del túnel de Postgres.
- [ ] **T5.1.4** Verificación end-to-end del cruce en el sitio — rama `chore/verificacion-cruce-vivo`
  - Reconstruir el stack con los datos vivos; confirmar que catálogo, numeralia y vistas ya no
    muestran el aviso "sin verificar contra producción" y que las discrepancias reales (si las
    hay) se ven correctamente.
  - CT: sitio reconstruido reflejando datos vivos; tablero actualizado (T5.1 completa).
  - Dependencias: T5.1.3.
