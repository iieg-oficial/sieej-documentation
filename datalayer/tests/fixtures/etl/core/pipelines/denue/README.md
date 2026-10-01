# denue

## Descripción general

Pipeline ETL del **Directorio Estadístico Nacional de Unidades Económicas** del INEGI.

> **Las coordenadas son las declaradas por el INEGI.** No se corrigen en el pipeline.

Se actualiza dos veces al año.

## Fuente general

https://www.inegi.org.mx/app/descarga/?ti=6

## Fuente específica

```shell
DENUE_URL=https://www.inegi.org.mx/contenidos/masiva/denue/denue_14_csv.zip
```

## Características de los datos

| Característica | Valor |
|---|---|
| Primer periodo disponible | `2010-07` |
| Frecuencia de actualización | Semestral |

## Diccionario de variables

### stg_denue

Una fila por unidad económica activa en Jalisco.

| variable | descripción |
|---|---|
| `id` | Clave del establecimiento |

### Catálogos

| tabla | contenido |
|---|---|
| `cat_sector` | Sectores SCIAN |

## Vistas

| vista | alcance |
|---|---|
| `v_establecimientos` | Establecimientos de Jalisco con su sector |

## Variables de entorno

| variable | descripción |
|---|---|
| `DENUE_URL` | URL del ZIP estatal |
