# Servicio builder: regenera data/*.json (Airflow + BD, solo lectura) y
# reconstruye el sitio Astro hacia el volumen que sirve nginx, de forma
# periódica. Contexto de build: la raíz del repositorio.

FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv rsync \
    && rm -rf /var/lib/apt/lists/*

COPY datalayer/ /opt/datalayer/
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir /opt/datalayer

COPY builder/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# /app y /sitio pertenecen a `node` (no-root, uid 1000) desde que se crean y
# cada COPY entra ya con ese dueño: un `chown -R` posterior duplicaría
# node_modules en una capa nueva y tardaría minutos en cada cambio de web/.
RUN mkdir -p /app /sitio && chown node:node /app /sitio

USER node
WORKDIR /app

COPY --chown=node:node web/package.json web/package-lock.json web/
RUN cd web && npm ci --no-audit --no-fund

COPY --chown=node:node web/ web/
COPY --chown=node:node data/ data/

ENV DATA_DIR=/app/data
ENV REBUILD_INTERVAL_SECONDS=86400

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
