# Arquitectura — Landing de documentación del SIEEJ

> Plan técnico del Agente Arquitecto. Estado: **propuesta, pendiente de aprobación**.
> Insumo: `data/inventario.json` (Agente Explorador, 2026-08-12 — parte viva pendiente de acceso de red).

## 1. Resumen del inventario

- **22 pipelines** inventariados a partir de la documentación estática.
- **22 HTML** de documentación (más `index.html` y 2 logos SVG en `assets/`); autocontenidos: CSS inline, sin dependencias externas de red, links relativos, ~11 MB en total.
- **53 vistas documentadas** en `views-md/` repartidas en 20 bases de datos (2 de ellas — `cvegeo`, `iieg` — son infraestructura geoespacial PostGIS, no pipelines).
- Cross check estático: 4 HTML sin vistas documentadas (`conapo`, `escuelas`, `ilmm`, `participacion_ciudadana`); 1 alias de nombre (`censos_economicos.html` ↔ BD `censo_economico`); 0 BDs de pipeline sin HTML.
- La verificación contra **Airflow y la BD de producción** (fuente de verdad) queda pendiente de acceso de red; el diseño no depende de ella, pero las cifras finales del catálogo sí.

## 2. Decisión: integración de los HTML de pipelines

**Elegida: (a) servirlos tal cual como páginas estáticas dentro del sitio.**

Los HTML se copian en build a `web/public/docs/` (junto con `assets/`) desde la ruta de origen configurada por variable de entorno (`DOCS_HTML_DIR`). El catálogo de la landing no lista archivos a mano: en build se hace *glob* del directorio y se cruza con el inventario.

Justificación:

- Son **autocontenidos** (CSS inline, sin JS externo, links relativos): funcionan sin tocar una línea.
- **Cero mantenimiento duplicado**: los HTML seguirán generándose fuera de este proyecto; un archivo nuevo aparece en el catálogo con solo reconstruir el sitio, sin cambios de código.
- Convertirlos a *content collections* (opción b) implicaría parsearlos/reescribirlos: frágil, con pérdida de fidelidad visual y mantenimiento duplicado cada vez que se regenere un HTML. Se descarta; el híbrido (c) hereda el mismo problema para la mitad convertida.

## 3. Decisión: capa de datos (build time vs. API vs. híbrido)

**Recomendada: Opción 1 — build time con reconstrucción periódica.** El híbrido (opción 3) queda como ruta de escalamiento documentada y barata gracias al módulo Python compartido.

Análisis:

| Criterio | 1. Build time | 2. API en vivo | 3. Híbrido |
|---|---|---|---|
| Frescura de numeralia | ≤ 24 h (cron diario) o minutos si Airflow dispara el rebuild al terminar corridas | TTL de caché (~15–30 min) | TTL de caché |
| Superficie hacia la BD | **Cero en runtime** (solo el builder, en red interna, en ventanas de build) | Servicio 24/7 conectado a la BD | Servicio 24/7 conectado a la BD |
| Servicios que operar | web (nginx) + builder programado | web + api | web + api + builder |
| Complejidad de despliegue | Mínima | Media | La mayor de las tres |

Los datos del sistema cambian al ritmo de las corridas de los pipelines (fuentes INEGI/CONAPO/SESNSP: mensuales, trimestrales o anuales; el snapshot de vistas de mayo 2026 sigue siendo representativo en agosto) y el alta de pipelines nuevos es esporádica. Una landing de documentación pública no necesita frescura intradía: la reconstrucción diaria — más un disparo opcional del rebuild desde Airflow al cierre de corridas exitosas — deja el retraso acotado a minutos/horas, con **cero superficie de ataque** hacia la BD en runtime y la operación más simple.

Condiciones que justificarían migrar al híbrido: necesidad de ver éxitos/fallos de corridas en tiempo real desde la landing (monitoreo operativo), o frecuencia de refresco que vuelva impráctico reconstruir. La migración no reescribe nada: la misma capa de datos Python se monta como app FastAPI (decisión tecnológica ya tomada: FastAPI + asyncpg + Pydantic v2 + uvicorn, caché TTL en memoria obligatoria, Redis solo como perfil opcional).

## 4. Estructura del monorepo

```
sieej-documentation/
├── docker-compose.yml
├── .env.example
├── web/                    # Astro (estático) + Dockerfile multi-stage (node → nginx)
│   ├── src/pages|components|layouts|styles/
│   └── public/docs/        # HTML de pipelines + assets (copiados en build, no versionados)
├── datalayer/              # Paquete Python reutilizable + Dockerfile del builder
│   ├── sieej_datalayer/    # airflow_client, db_introspect, crosscheck, cli
│   └── tests/
├── data/                   # JSON generados (inventario, numeralia, vistas)
├── docs/                   # arquitectura.md, tasks.md, convenciones
└── .claude/agents/         # definición de los 6 agentes
```

## 5. Contrato de datos (salida de `datalayer`, consumida por Astro en build)

- `data/inventario.json` — por pipeline: documentación estática (HTML, vistas documentadas) + fuente viva (DAG, estado, última corrida; BD y vistas reales) + clasificación: `documentado` / `documentacion_pendiente` / `posible_desactualizado`.
- `data/numeralia.json` — cifras de Airflow (DAGs activos, corridas recientes, éxitos/fallos, última ejecución) y de BD (nº de vistas materializadas, registros por vista/esquema, última actualización), más el bloque `cross_check` con las discrepancias detectadas entre Airflow ↔ BD ↔ documentación estática.
- `data/vistas.json` — por base de datos: vistas/matviews con columnas, tipos y comentarios vía introspección (`pg_matviews`, `pg_views`, `information_schema.columns`, `col_description`), enriquecidas con descripciones de `views-md/` solo cuando coinciden; banderas `solo_en_bd` / `solo_en_docs`.

Reglas de degradación: si Airflow o la BD no responden durante el build, se reutiliza el último JSON válido y se marca `datos_obsoletos: true` con su fecha — el build **nunca** falla por fuentes caídas, y la landing muestra la antigüedad de los datos.

## 6. Infraestructura (Docker Compose)

- **`web`**: build multi-stage — etapa Node ejecuta `datalayer` (refresco de JSON) + `astro build`; etapa final nginx sirviendo `dist/`, usuario no-root, healthcheck HTTP.
- **`builder`**: imagen Python slim + Node con `supercronic`; en el cron configurado (`REBUILD_CRON`, propuesta: diario 06:00) regenera los JSON y reconstruye el sitio hacia el volumen que `web` sirve. Expone además un endpoint mínimo de *webhook* opcional para que Airflow dispare el rebuild al terminar corridas.
- **`api`** (no incluido por defecto): definición documentada para la migración al híbrido; **`redis`** solo como perfil `--profile cache`.
- Configuración exclusivamente por `env_file`; `.env.example` completo. La BD y Airflow son externos: los contenedores solo necesitan alcanzar `iieg-db-etl:5432` (PostgreSQL, usuario de solo lectura) y la API REST de Airflow en la red interna — a documentar en el README.

Restricciones duras que el diseño respeta: la BD **nunca** se expone al navegador (el cliente solo recibe JSON estático); credenciales solo por variables de entorno; todo acceso de solo lectura; ninguna visita a la landing toca la BD.

## 7. Orden de implementación

1. **git-flujo**: `.gitignore`, `CONTRIBUTING.md`, plantilla de PR, pre-commit, `docs/tasks.md` con el desglose atómico.
2. **datalayer** (paralelo con web): clientes Airflow/PostgreSQL, cross check, CLI, degradación, tests.
3. **web** (paralelo con datalayer): scaffold Astro, layout y sistema de diseño, sección SIEEJ, catálogo, numeralia, vistas.
4. **Infra**: Dockerfiles, compose, healthchecks, rebuild programado.
5. **qa-revisor**: verificación contra los criterios de aceptación.

Dependencias externas antes del paso 2: acceso de red a Airflow y BD (VPN o ejecución desde red interna), credenciales de la API de Airflow y cadena de conexión de solo lectura — por `.env`, nunca en el repo.
