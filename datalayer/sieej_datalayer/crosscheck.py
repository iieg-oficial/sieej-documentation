"""Cruce Airflow ↔ BD de producción ↔ documentación estática.

Las fuentes vivas mandan: la documentación solo enriquece. Toda discrepancia
se reporta de forma explícita para que la landing la muestre, no la oculte.
"""

from datetime import datetime, timezone

from .db_introspect import VISTAS_SISTEMA_POSTGIS
from .models import (
    BaseDeDatos,
    ClasificacionPipeline,
    Dag,
    DocumentacionHtml,
    EstadoFuente,
    EstructuraVistas,
    Fuente,
    Inventario,
    Numeralia,
    Pipeline,
    Vista,
)
from .static_docs import ALIAS_NOMBRE_A_BD

_PREFIJOS_DAG = ("etl_", "dag_", "pipeline_")
# Sufijos que nombran la etapa, no el pipeline: etl_denue_update es la etapa
# "update" del pipeline "denue", no un pipeline aparte.
_SUFIJOS_ETAPA = ("bootstrap", "update", "incremental")
# Orden con el que se listan las etapas de un pipeline: carga inicial, luego la
# actualización, luego la carga incremental. Es el orden de la tupla de arriba.
# Lo demás va al final.
_ORDEN_ETAPA = {etapa: i for i, etapa in enumerate(_SUFIJOS_ETAPA)}


def _normalizar_dag_id(dag_id: str) -> str:
    nombre = dag_id.lower()
    for prefijo in _PREFIJOS_DAG:
        if nombre.startswith(prefijo):
            return nombre[len(prefijo) :]
    return nombre


def partir_dag_id(dag_id: str) -> tuple[str, str | None]:
    """Separa un dag_id en (pipeline, etapa), ya normalizado y con alias resueltos.

    `etl_denue_update` -> `("denue", "update")`; `etl_conapo` -> `("conapo", None)`.
    Los alias de nombre (plural/singular entre fuentes) se resuelven aquí para
    que un DAG empate con su base aunque se llamen distinto.
    """
    nombre = _normalizar_dag_id(dag_id)
    etapa = None
    for sufijo in _SUFIJOS_ETAPA:
        if nombre.endswith(f"_{sufijo}"):
            nombre, etapa = nombre[: -len(sufijo) - 1], sufijo
            break
    return ALIAS_NOMBRE_A_BD.get(nombre, nombre), etapa


def _dags_fuera_de_convencion(dags: dict[str, Dag], conocidos: set[str]) -> list[str]:
    """DAG cuyo nombre no sigue la convención de ETL-SIEEJ y no empata con nada.

    La convención está escrita aguas arriba: `etl_{flujo}_bootstrap` y
    `etl_{flujo}_update` en `.github/skills/dag-airflow/SKILL.md`, más la
    variante `incremental` en `docs/architecture.md`. Un dag_id que no termine
    en ninguno de los tres no se puede partir en (pipeline, etapa), y como el
    emparejamiento acepta nombres derivados de los DAG, terminaría creando un
    pipeline inventado —`etl_denue_backfill` daría un pipeline `denue_backfill`,
    con DAG pero sin base ni ficha, mientras `denue` pierde esa etapa—.

    No basta con exigir sufijo: `etl_conapo` es legítimo si `conapo` ya es un
    pipeline conocido. Se reporta solo lo que además no empata con nada.
    """
    return sorted(
        dag_id
        for dag_id in dags
        if partir_dag_id(dag_id)[1] is None
        and partir_dag_id(dag_id)[0] not in conocidos
        and dag_id not in conocidos
    )


def emparejar_dags(nombres: set[str], dags: dict[str, Dag]) -> dict[str, list[Dag]]:
    """Agrupa los DAG por pipeline: cada pipeline conserva todas sus etapas.

    `nombres` acota a qué pipelines conocidos se puede emparejar; un dag_id que
    coincida literalmente con un nombre también empata, sin partir la etapa.
    """
    por_nombre: dict[str, list[Dag]] = {}
    for dag_id, dag in sorted(dags.items()):
        pipeline, etapa = partir_dag_id(dag_id)
        if pipeline in nombres:
            por_nombre.setdefault(pipeline, []).append(dag.model_copy(update={"etapa": etapa}))
        elif dag_id in nombres:
            por_nombre.setdefault(dag_id, []).append(dag)
    for etapas in por_nombre.values():
        etapas.sort(key=lambda d: (_ORDEN_ETAPA.get(d.etapa or "", len(_ORDEN_ETAPA)), d.dag_id))
    return por_nombre


def _clasificar(p: Pipeline, vivas_ok: bool) -> ClasificacionPipeline:
    if not vivas_ok:
        return ClasificacionPipeline.SIN_VERIFICAR
    vivo = bool(p.bd_existe) or bool(p.etapas)
    if vivo and p.documentacion_html:
        return ClasificacionPipeline.DOCUMENTADO
    if vivo:
        return ClasificacionPipeline.DOCUMENTACION_PENDIENTE
    return ClasificacionPipeline.POSIBLE_DESACTUALIZADO


def construir_inventario(
    fuentes: dict[str, Fuente],
    html_docs: dict[str, DocumentacionHtml],
    vistas_docs: dict[str, list[Vista]],
    dags: dict[str, Dag],
    bases: list[BaseDeDatos],
    generado: datetime | None = None,
) -> Inventario:
    generado = generado or datetime.now(timezone.utc)
    bd_ok = fuentes.get("bd", Fuente(estado=EstadoFuente.SIN_CONFIGURAR)).estado
    airflow_ok = fuentes.get("airflow", Fuente(estado=EstadoFuente.SIN_CONFIGURAR)).estado
    vivas_ok = EstadoFuente.OK in (bd_ok, airflow_ok)

    bases_pipeline = {b.nombre: b for b in bases if not b.es_infraestructura}
    bases_docs = {bd for bd in vistas_docs if not _es_infra_docs(vistas_docs[bd])}

    nombres = set(html_docs) | set(bases_pipeline) | bases_docs
    # Se cuelan los nombres derivados de los DAG para que un pipeline que solo
    # existe en Airflow —recién desplegado, sin base ni ficha— también aparezca.
    # El precio es que un dag_id fuera de convención se vuelve un pipeline
    # inventado en silencio; `dags_fuera_de_convencion` es lo que lo delata.
    fuera_de_convencion = _dags_fuera_de_convencion(dags, nombres)
    dags_por_nombre = emparejar_dags(nombres | {partir_dag_id(d)[0] for d in dags}, dags)
    nombres |= set(dags_por_nombre)

    pipelines: dict[str, Pipeline] = {}
    for nombre in sorted(nombres):
        base_viva = bases_pipeline.get(nombre)
        p = Pipeline(
            nombre=nombre,
            documentacion_html=html_docs.get(nombre),
            alias_html=_alias_de(nombre, html_docs),
            vistas_documentadas=[v.nombre for v in vistas_docs.get(nombre, [])],
            etapas=dags_por_nombre.get(nombre, []),
            bd_existe=(nombre in bases_pipeline) if bd_ok == EstadoFuente.OK else None,
            vistas_en_bd=len(base_viva.vistas) if base_viva else None,
        )
        p.clasificacion = _clasificar(p, vivas_ok)
        pipelines[nombre] = p

    dags_sin_pipeline = sorted(
        d for d in dags if partir_dag_id(d)[0] not in pipelines and d not in pipelines
    )
    cross_check = {
        "pipelines_sin_html": sorted(
            n for n, p in pipelines.items() if p.documentacion_html is None
        ),
        "html_sin_pipeline_vivo": sorted(
            n
            for n, p in pipelines.items()
            if p.documentacion_html
            and p.clasificacion is ClasificacionPipeline.POSIBLE_DESACTUALIZADO
        ),
        "dags_sin_pipeline": dags_sin_pipeline,
        "dags_fuera_de_convencion": fuera_de_convencion,
        "alias_nombres": {p.alias_html: n for n, p in pipelines.items() if p.alias_html},
    }
    resumen = {
        "pipelines": len(pipelines),
        "con_html": sum(1 for p in pipelines.values() if p.documentacion_html),
        "dags_emparejados": sum(len(e) for e in dags_por_nombre.values()),
        "pipelines_con_etapas": len(dags_por_nombre),
        "dags_fuera_de_convencion": len(fuera_de_convencion),
        "bases_en_bd": len(bases_pipeline) if bd_ok == EstadoFuente.OK else None,
        "verificado_contra_produccion": vivas_ok,
    }
    return Inventario(
        generado=generado,
        fuentes=fuentes,
        resumen=resumen,
        cross_check=cross_check,
        pipelines=pipelines,
    )


def _alias_de(nombre: str, html_docs: dict[str, DocumentacionHtml]) -> str | None:
    doc = html_docs.get(nombre)
    if doc and doc.archivo != f"{nombre}.html":
        return doc.archivo.removesuffix(".html")
    return None


def _es_infra_docs(vistas: list[Vista]) -> bool:
    return bool(vistas) and all(v.nombre in VISTAS_SISTEMA_POSTGIS for v in vistas)


def construir_numeralia(
    fuentes: dict[str, Fuente],
    inventario: Inventario,
    dags: dict[str, Dag],
    bases: list[BaseDeDatos],
    vistas_docs: dict[str, list[Vista]],
    generado: datetime | None = None,
) -> Numeralia:
    generado = generado or datetime.now(timezone.utc)
    bd_ok = fuentes.get("bd", Fuente(estado=EstadoFuente.SIN_CONFIGURAR)).estado
    airflow_ok = fuentes.get("airflow", Fuente(estado=EstadoFuente.SIN_CONFIGURAR)).estado

    bases_pipeline = [b for b in bases if not b.es_infraestructura]
    airflow = {}
    if airflow_ok == EstadoFuente.OK:
        ultimas = [
            d.ultima_corrida_fecha for d in dags.values() if d.ultima_corrida_fecha is not None
        ]
        airflow = {
            "dags_total": len(dags),
            "dags_activos": sum(1 for d in dags.values() if d.pausado is False),
            "dags_pausados": sum(1 for d in dags.values() if d.pausado),
            "corridas_recientes_exitos": sum(
                d.corridas_recientes.exitos for d in dags.values() if d.corridas_recientes
            ),
            "corridas_recientes_fallos": sum(
                d.corridas_recientes.fallos for d in dags.values() if d.corridas_recientes
            ),
            "ultima_ejecucion": max(ultimas).isoformat() if ultimas else None,
        }
    bd = {}
    if bd_ok == EstadoFuente.OK:
        vistas_vivas = [v for b in bases_pipeline for v in b.vistas]
        bd = {
            "bases_pipeline": len(bases_pipeline),
            "bases_infraestructura": len(bases) - len(bases_pipeline),
            "vistas_total": len(vistas_vivas),
            "matviews_total": sum(1 for v in vistas_vivas if v.tipo == "MATERIALIZED VIEW"),
            "registros_totales": sum(v.registros or 0 for v in vistas_vivas),
        }
    documentacion = {
        "html_pipelines": inventario.resumen.get("con_html", 0),
        "bases_documentadas": sum(1 for bd_ in vistas_docs.values() if not _es_infra_docs(bd_)),
        "vistas_documentadas": sum(len(v) for k, v in vistas_docs.items() if not _es_infra_docs(v)),
    }

    discrepancias: list[str] = []
    cifras = {
        "pipelines_documentados": documentacion["html_pipelines"],
        "dags_activos": airflow.get("dags_activos"),
        "bases_con_vistas": bd.get("bases_pipeline"),
    }
    comparables = [v for v in cifras.values() if v is not None]
    consistente = len(set(comparables)) <= 1
    if not consistente:
        discrepancias.append(
            "Las cifras de documentación, Airflow y BD no coinciden: "
            + ", ".join(f"{k}={v}" for k, v in cifras.items() if v is not None)
        )
    for clave in ("pipelines_sin_html", "html_sin_pipeline_vivo", "dags_sin_pipeline"):
        elementos = inventario.cross_check.get(clave, [])
        if elementos:
            discrepancias.append(f"{clave}: {', '.join(elementos)}")

    return Numeralia(
        generado=generado,
        fuentes=fuentes,
        airflow=airflow,
        bd=bd,
        documentacion=documentacion,
        cross_check={
            "consistente": consistente and not discrepancias,
            "cifras": cifras,
            "discrepancias": discrepancias,
        },
    )


def construir_estructura_vistas(
    fuentes: dict[str, Fuente],
    bases: list[BaseDeDatos],
    vistas_docs: dict[str, list[Vista]],
    generado: datetime | None = None,
) -> EstructuraVistas:
    """Estructura por base: la introspección manda, los markdown enriquecen."""
    generado = generado or datetime.now(timezone.utc)
    bd_ok = fuentes.get("bd", Fuente(estado=EstadoFuente.SIN_CONFIGURAR)).estado

    if bd_ok != EstadoFuente.OK:
        # Degradación: solo documentación estática, marcada como no verificada.
        resultado = [
            BaseDeDatos(nombre=bd, es_infraestructura=_es_infra_docs(vistas), vistas=vistas)
            for bd, vistas in sorted(vistas_docs.items())
        ]
        return EstructuraVistas(generado=generado, fuentes=fuentes, bases=resultado)

    resultado: list[BaseDeDatos] = []
    for base in sorted(bases, key=lambda b: b.nombre):
        docs = {v.nombre: v for v in vistas_docs.get(base.nombre, [])}
        vistas: list[Vista] = []
        for vista in base.vistas:
            doc = docs.pop(vista.nombre, None)
            vista = vista.model_copy(deep=True)
            vista.en_docs = doc is not None
            vista.solo_en_bd = doc is None and vista.nombre not in VISTAS_SISTEMA_POSTGIS
            if doc:
                vista.archivo_md = doc.archivo_md
            vistas.append(vista)
        for doc in docs.values():  # documentadas pero ya no existen en la BD
            doc = doc.model_copy(deep=True)
            doc.en_bd = False
            doc.solo_en_docs = True
            vistas.append(doc)
        resultado.append(
            BaseDeDatos(
                nombre=base.nombre, es_infraestructura=base.es_infraestructura, vistas=vistas
            )
        )

    vivas = {b.nombre for b in bases}
    for bd, vistas in sorted(vistas_docs.items()):  # bases documentadas ausentes de la BD
        if bd not in vivas:
            marcadas = []
            for v in vistas:
                v = v.model_copy(deep=True)
                v.en_bd = False
                v.solo_en_docs = True
                marcadas.append(v)
            resultado.append(
                BaseDeDatos(nombre=bd, es_infraestructura=_es_infra_docs(vistas), vistas=marcadas)
            )
    return EstructuraVistas(generado=generado, fuentes=fuentes, bases=resultado)
