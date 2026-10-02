FROM node:22-slim AS construccion

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build && npm prune --omit=dev

FROM node:22-slim

ENV NODE_ENV=production HOST=0.0.0.0 PORT=8080 DATA_DIR=/app/data
WORKDIR /app/web
COPY --from=construccion --chown=node:node /app/web/node_modules ./node_modules
COPY --from=construccion --chown=node:node /app/web/dist ./dist
COPY --from=construccion --chown=node:node /app/web/package.json ./package.json
USER node
EXPOSE 8080
CMD ["node", "dist/server/entry.mjs"]
