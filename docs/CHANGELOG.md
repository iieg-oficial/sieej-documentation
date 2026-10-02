# Changelog

Todos los cambios notables en este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y el proyecto
adhiere a [Semantic Versioning](https://semver.org/lang/es/). La versión vive en `web/package.json`.

## [0.2.0] - 2026-10-02

### Agregado

- Entrada al ecosistema IIEG (frente 18 de tamal-rojo): `compose.yaml` con `compose.dev.yaml` y `compose.prod.yaml`, `make up` / `make deploy` con `make/common.mk`, `.env.development` y `.env.production`
- **Sincronización con mariachi**: cada ciclo envía a `PUT /api/public/sieej-documentacion/sync` el README, las tablas, vistas, relaciones y DAGs de cada pipeline. `make mariachi-key` genera la clave y la huella
- **Detección automática de pipelines** por base en la BD, README, carpeta en `core/pipelines` de ETL-SIEEJ o DAG en Airflow; un pipeline nuevo aparece en el siguiente ciclo
- Telemetría de visitas hacia mariachi desde el servidor y `/ontoy` (contrato v2) con la frescura de la sincronización y la salud de mariachi

### Cambiado

- El sitio pasa a **Astro en modo servidor** (`@astrojs/node`): las páginas de pipeline salen de la API pública de mariachi con caché por token de versión y respaldo en lo último bueno o en `data/`
- El builder ya no compila el sitio: es una imagen Python que solo corre el datalayer
- Las redirecciones de `/docs/*.html` y `/salud` pasan de nginx a Astro

### Eliminado

- nginx del servicio `web` y el volumen `sitio`
- `docker-compose.yml`
