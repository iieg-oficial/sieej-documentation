# Contexto de sesión — Landing SIEEJ (hasta 2026-08-17)

> Resumen de lo construido en las sesiones previas de Claude Code, para retomar el trabajo sin
> tener que releer todo el historial de conversación. Complementa (no sustituye) a
> `docs/arquitectura.md` (plan técnico) y `docs/tasks.md` (tablero de tareas, fuente de verdad
> del estado tarea por tarea).

## Qué es esto

Landing de documentación pública del **SIEEJ** (IIEG, Jalisco): qué es el sistema, catálogo de
pipelines ETL en producción, numeralia con cross check Airflow↔BD, y estructura de vistas
materializadas. Repo: `iieg-oficial/sieej-documentation` (GitHub), rama `main` protegida.

## Estado: 25/26 tareas completadas

`docs/tasks.md` tiene 25 tareas en `[x]`. La única pendiente:

- **T5.1 — Inventario vivo**: cruzar `data/*.json` contra Airflow y la BD de producción reales.
  Bloqueado porque los servidores (`iieg-db-etl`, `iieg-airflow`) están en la red interna del
  IIEG (`10.13.x.x`), inalcanzable desde esta máquina sin VPN. Los hosts SSH ya están
  configurados en `~/.ssh/config`. En cuanto haya acceso de red: llenar `.env` (credenciales de
  solo lectura, ver `.env.example`) y correr `.venv/bin/python -m sieej_datalayer` o dejar que
  el servicio `builder` de Compose lo haga en su próximo ciclo. Hasta entonces, todo el sitio
  corre en **modo degradado**: el catálogo y la numeralia muestran los datos de la
  documentación estática y se marcan explícitamente como "sin verificar contra producción".

Todo el trabajo entró por **25 PRs mergeadas** (una tarea = una rama = una PR, Conventional
Commits en inglés por regla del repo). Ramas ya borradas local y remotamente tras cada merge.

## Arquitectura (resumen — detalle completo en `docs/arquitectura.md`)

- **Build time con reconstrucción periódica** (no API en vivo): un paquete Python
  (`datalayer/`) consulta Airflow + PostgreSQL, cruza con la documentación estática, y genera
  `data/*.json`. Astro (`web/`) los lee en build. Reconstrucción automática vía el servicio
  `builder` de Docker Compose (cron interno, `REBUILD_INTERVAL_SECONDS`).
- **HTML de pipelines servidos tal cual**: `web/scripts/copy-docs.mjs` copia los ~22 HTML desde
  `DOCS_HTML_DIR` (fuera del repo, en `general-documentation/`) a `web/public/docs/` en cada
  build. Absorbe archivos nuevos sin tocar código.
- **Docker Compose**: `web` (nginx no-root sirviendo el sitio) + `builder` (Python + Node,
  regenera datos y reconstruye el sitio) + `redis` opcional (perfil `cache`, no usado). La BD y
  Airflow son externos, no se levantan en Compose.
- Stack corriendo localmente en **http://localhost:18081** (contenedores `sieej-documentation-web-1`
  y `sieej-documentation-builder-1`, ambos `healthy`).

## Estructura del repo

```
sieej-documentation/
├── docker-compose.yml, .env.example, .dockerignore
├── web/                 # Astro — landing, layout, secciones, copy-docs.mjs
│   ├── src/components/  # SeccionSieej.astro, SeccionCatalogo.astro, SeccionNumeralia.astro
│   ├── src/pages/        # index.astro, vistas/index.astro, vistas/[bd].astro
│   ├── public/{fonts,logos,img}/  # Poppins/JetBrains Mono autoalojadas, logos IIEG/Jalisco
│   └── Dockerfile, nginx/default.conf
├── datalayer/            # paquete Python sieej_datalayer + 29 tests (pytest)
├── builder/               # Dockerfile + entrypoint.sh del servicio de reconstrucción
├── data/                  # inventario.json, numeralia.json, vistas.json (generados)
├── docs/                  # arquitectura.md, tasks.md, convencion-commits.md, este archivo
└── .claude/agents/        # 6 agentes del proyecto (explorador, arquitecto, git-flujo,
                            #  frontend-astro, datos-backend, qa-revisor)
```

## Cambios de contenido recientes (sesión de ajustes visuales, PRs #16–#25)

Después de que el sitio quedó funcionalmente completo (PR #15, QA), el trabajo se centró en
ajustes de identidad visual y texto de la sección "El SIEEJ":

1. **Identidad visual (#16)**: tipografía Poppins + JetBrains Mono (autoalojadas en
   `web/public/fonts/`), logos IIEG/Jalisco (`web/public/logos/`) en hero y footer,
   homologados con los HTML de `docs/` (se les inyecta el mismo `@font-face` en
   `copy-docs.mjs`, sin tocar los archivos fuente).
2. **Retiro del índice de pipelines (#17, #18)**: `docs/index.html` ya no se copia; `/docs/`
   redirige (301 relativo) al catálogo del home (`/#catalogo`).
3. **Texto curado (#19)**: definición y objetivos de `definiciones_sieej_para_landing.md`.
4. **Diagramas (#20, #21, #22)**: se agregó el diagrama general del SIEEJ y el diagrama de
   flujo de datos (`SIEEJ_1.svg`, 3 MB por PNGs embebidos → convertido a WebP de 115 KB) dentro
   de una nueva tarjeta "Características del SIEEJ", con resúmenes de las explicaciones del
   documento fuente y el orden: párrafo → diagrama → párrafo → diagrama.
5. **Retiro de tarjeta (#23)**: se quitó "¿Qué es un flujo ETL?".
6. **Texto definitivo (#24)**: toda la sección "El SIEEJ" reescrita con el texto de
   `texto_mejorado_para_landing_sieej.md` (fuente definitiva, reemplaza versiones previas).
7. **Limpieza de negritas (#25)**: se quitaron todas las negritas del texto excepto
   `Mirador IIEG` en "Tecnologías del sistema", a pedido explícito del usuario.

El componente `web/src/components/SeccionSieej.astro` es el que más ha cambiado; su fuente de
verdad actual es `texto_mejorado_para_landing_sieej.md` en `general-documentation/`.

## Decisiones y matices que vale la pena recordar

- **Identidad visual**: paleta y tipografía tomadas de `04_identidad_visual.md` en
  `~/Documentos/IIEG/curso-gestion-informacion/context/` (no es específico de SIEEJ, es el
  manual de marca general del IIEG usado también en cursos).
- **`SIEEJ_1.svg` pesa 3 MB** porque envuelve 2 PNG en base64 (no es vectorial real). Se sirve
  como WebP regenerado desde el PNG fuente — mismo contenido visual, 96% más liviano.
- El hook de pre-commit (`check-added-large-files`, límite 1 MB) fue lo que detectó el
  problema del SVG — vale la pena confiar en sus bloqueos, no saltárselos.
- El fix del redirect relativo (`absolute_redirect off` en nginx) surgió porque el primer
  intento del redirect de `/docs/` devolvía el puerto interno del contenedor (8080) en vez del
  puerto público mapeado — se detectó probando el stack real, no solo el build.
- Reglas del repo (`.claude/rules/commits.md`): commits con encabezado solo, en inglés
  imperativo (Conventional Commits), sin `Co-Authored-By`. Identidad de commits: Renato
  Salomon Arroyo Duarte <renato.arroyo@iieg.gob.mx> (config local del repo); `gh` autenticado
  como `renatoarroyo-iieg`.

## Cómo retomar el trabajo

```bash
cd ~/Documentos/IIEG/sieej/sieej-documentation
docker compose up -d --build   # si el stack no está corriendo
# sitio en http://localhost:18081
```

Para cambios de contenido en la sección SIEEJ: editar
`web/src/components/SeccionSieej.astro` y cotejar contra
`~/Documentos/IIEG/sieej/general-documentation/texto_mejorado_para_landing_sieej.md`.

Para cualquier cambio: seguir el flujo `CONTRIBUTING.md` — una tarea nueva en `docs/tasks.md`,
rama `feature/*`/`update/*`/`fix/*`, PR, merge, borrar rama. `npm run build` en `web/` y
`pytest` en `datalayer/` antes de cada PR.
