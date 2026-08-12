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

## Fase 3 — Infraestructura (agentes: datos-backend + git-flujo)

- [ ] **T3.1** Dockerfile de `web` — rama `chore/docker-web`
  - Multi-stage: Node (datos + `astro build`) → nginx sirviendo `dist/`, usuario no-root,
    healthcheck HTTP.
  - CT: `docker build` y contenedor sano sirviendo el sitio.
  - Dependencias: T2.4.
- [ ] **T3.2** Servicio `builder` con reconstrucción programada — rama `chore/docker-builder`
  - Imagen Python+Node con supercronic; `REBUILD_CRON` regenera JSON y reconstruye el
    sitio al volumen servido; webhook opcional para disparo desde Airflow.
  - CT: una corrida del builder reconstruye el sitio end-to-end en local.
  - Dependencias: T1.4, T3.1.
- [ ] **T3.3** `docker-compose.yml` + `.env.example` + README — rama `chore/compose`
  - Compose raíz con healthchecks y `depends_on` condicionado; `.env.example` completo;
    README con arquitectura, arranque y accesos de red requeridos (BD y Airflow externos).
  - CT: `docker compose up` levanta el sistema completo con healthchecks en verde.
  - Dependencias: T3.1, T3.2.

## Fase 4 — QA (agente: qa-revisor)

- [ ] **T4.1** Verificación de criterios de aceptación — sin rama (solo lectura)
  - Build limpio, links a los 22 HTML, sin secretos en código ni historial, accesibilidad,
    fidelidad del contenido, convenciones de git, tablero al día.
  - CT: reporte con hallazgos por severidad; bloqueantes en cero.
  - Dependencias: todas las anteriores.

## Pendiente de acceso de red (bloqueadas)

- [ ] **T5.1** Inventario vivo: cruce real contra Airflow y BD de producción
  - Ejecutar `datalayer` con acceso a `iieg-airflow` / `iieg-db-etl` y regenerar los JSON.
  - Dependencias: T1.4 + acceso de red (VPN o ejecución en red interna) + credenciales por `.env`.
