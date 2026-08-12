# Guía de contribución — sieej-documentation

## Estrategia de ramas (GitHub flow)

- `main` es la rama protegida: **nunca** se commitea directo a ella.
- Cada tarea del tablero (`docs/tasks.md`) se trabaja en su propia rama:
  `feature/*` (funcionalidad), `fix/*` (correcciones), `docs/*` (documentación), `chore/*` (config/infra).
- Regla de oro: **una tarea = una rama = una PR**. PRs pequeñas, con objetivo único y criterio de terminado verificable.
- Toda PR referencia su tarea del tablero y actualiza su checkbox al mergear.

## Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/) según la convención del equipo
([docs/convencion-commits.md](docs/convencion-commits.md)):

- Formato: `<tipo>(<scope>): <descripción en imperativo, en inglés>` (máx. 72 caracteres).
- Tipos: `feat`, `fix`, `update`, `refactor`, `chore`, `docs`, `merge`.
- Solo la línea de encabezado: sin cuerpo ni descripción adicional.
- Commits atómicos: un commit = un cambio lógico. Sin commits `WIP` en la PR final.

Scopes de este repositorio: `web` (Astro), `datalayer` (Python), `docker`, `config`, `docs`, `agents`.

## Seguridad

- **Ninguna credencial ni cadena de conexión entra al repositorio**, nunca: todo por `.env`
  (fuera de git) documentado en `.env.example`.
- Todo acceso a Airflow y a la BD de producción es de **solo lectura**.
- Los hooks de pre-commit incluyen detección de secretos; instálalos antes del primer commit:

```bash
pip install pre-commit && pre-commit install
```

## Flujo de una tarea

1. Toma una tarea disponible (sin dependencias abiertas) en `docs/tasks.md`.
2. `git switch -c <tipo>/<nombre-corto>` desde `main` actualizado.
3. Implementa, con commits atómicos y build limpio (`npm run build` en `web/`, `pytest` en `datalayer/`).
4. Abre la PR con la plantilla, referenciando la tarea; mergea cuando pase la revisión.
5. Marca la tarea como completada en `docs/tasks.md`.
