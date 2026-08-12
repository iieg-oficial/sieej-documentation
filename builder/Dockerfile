# Servicio builder: regenera data/*.json (Airflow + BD, solo lectura) y
# reconstruye el sitio Astro hacia el volumen que sirve nginx, de forma
# periódica. Contexto de build: la raíz del repositorio.

FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv rsync \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY datalayer/ datalayer/
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir ./datalayer

COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci --no-audit --no-fund

COPY web/ web/
COPY data/ data/
COPY builder/entrypoint.sh /usr/local/bin/entrypoint.sh

# /sitio: destino del sitio construido (volumen compartido con nginx).
# El usuario `node` (no-root, uid 1000) debe poder escribir ambos.
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /sitio \
    && chown -R node:node /app /sitio

USER node

ENV DATA_DIR=/app/data
ENV REBUILD_INTERVAL_SECONDS=86400

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
