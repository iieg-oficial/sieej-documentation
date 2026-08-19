# Runbook — verificación end-to-end del cruce vivo (T5.1.4)

> Bloqueada por T5.1.3 (`feature/datalayer-cruce-vivo`, PR #38). No ejecutar hasta que esa
> tarea complete y los `data/*.json` reflejen fuentes vivas reales.

## Pasos

```bash
# 1. Con data/*.json ya regenerados desde fuentes vivas (T5.1.3), reconstruir el stack
docker compose up -d --build

# 2. Verificar que el aviso "sin verificar contra producción" ya no aparece
curl -s http://localhost:${WEB_PORT:-8080}/ | grep -c "sin verificar contra producción" \
  && echo "AÚN aparece el aviso — revisar" || echo "aviso ausente, correcto"

# 3. Revisar visualmente el catálogo (insignias por pipeline), la numeralia (cifras y
#    discrepancias) y la estructura de vistas (/vistas/) contra lo que reportan Airflow y la
#    BD reales.
```

## Criterio de terminado

- Sitio reconstruido reflejando datos vivos (sin el aviso de "sin verificar").
- Catálogo, numeralia y vistas muestran las cifras reales; cualquier discrepancia real entre
  Airflow/BD/documentación estática es visible, no oculta.
- `docs/tasks.md`: T5.1.1, T5.1.2, T5.1.3 y T5.1.4 marcadas `[x]`; la sección "Fase 5" queda
  completa.

## Al completar

Borrar este runbook y el de T5.1.3 (`docs/runbook-cruce-vivo.md`) — su contenido pasa a ser
historia de commits una vez ejecutados.
