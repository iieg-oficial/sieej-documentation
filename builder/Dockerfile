FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home sincronizador

COPY datalayer/ /opt/datalayer/
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir /opt/datalayer

COPY builder/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/data /app/etl \
    && chown sincronizador:sincronizador /app /app/data /app/etl

COPY --chown=sincronizador:sincronizador data/ /app/data/

USER sincronizador
WORKDIR /app

ENV DATA_DIR=/app/data
ENV REBUILD_INTERVAL_SECONDS=86400

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
