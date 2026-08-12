# Landing SIEEJ — imagen del servicio web.
# Multi-stage: Node construye el sitio estático; nginx sin privilegios lo sirve.
# Contexto de build: la raíz del repositorio (necesita ../data del sitio).

FROM node:22-slim AS construccion

WORKDIR /app
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci --no-audit --no-fund

COPY data/ data/
COPY web/ web/
# Build de respaldo horneado en la imagen (sin DOCS_HTML_DIR: degrada con aviso).
# El servicio builder lo reemplaza con el sitio completo en el volumen compartido.
RUN cd web && npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine

COPY web/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=construccion /app/web/dist /usr/share/nginx/html

# La imagen base ya corre como usuario no-root (uid 101) y escucha en 8080.
EXPOSE 8080
