"""Capa de datos de la landing de documentación del SIEEJ.

Consulta Airflow (API REST) y PostgreSQL de producción (solo lectura),
cruza ambas fuentes con la documentación estática y genera los JSON que
consume el sitio Astro en build time. Si una fuente viva no responde,
degrada con gracia reutilizando el último JSON válido.
"""

__version__ = "0.1.0"
