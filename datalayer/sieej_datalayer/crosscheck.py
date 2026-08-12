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

_PREFIJOS_DAG = ("etl_", "dag_", "pipeline_")


def _normalizar_dag_id(dag_id: str) -> str:
    nombre = dag_id.lower()
    for prefijo in _PREFIJOS_DAG:
        if nombre.startswith(prefijo):
            return nombre[len(prefijo) :]
    return nombre


def emparejar_dags(nombres: set[str], dags: dict[str, Dag]) -> dict[str, Dag]:
    """Asigna cada DAG a su pipeline por nombre normalizado (etl_denue -> denue)."""
    por_nombre: dict[str, Dag] = {}
    for dag_id, dag in dags.items():
        normalizado = _normalizar_dag_id(dag_id)
        if normalizado in nombres:
            por_nombre[normalizado] = dag
        elif dag_id in nombres:
            por_nombre[dag_id] = dag
    return por_nombre


def _clasificar(p: Pipeline, vivas_ok: bool) -> ClasificacionPipeline:
    if not vivas_ok:
        return ClasificacionPipeline.SIN_VERIFICAR
    vivo = bool(p.bd_existe) or p.dag is not None
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
    dags_por_nombre = emparejar_dags(nombres | {_normalizar_dag_id(d) for d in dags}, dags)
    nombres |= set(dags_por_nombre)

    pipelines: dict[str, Pipeline] = {}
    for nombre in sorted(nombres):
        base_viva = bases_pipeline.get(nombre)
        p = Pipeline(
            nombre=nombre,
            documentacion_html=html_docs.get(nombre),
            alias_html=_alias_de(nombre, html_docs),
            vistas_documentadas=[v.nombre for v in vistas_docs.get(nombre, [])],
            dag=dags_por_nombre.get(nombre),
            bd_existe=(nombre in bases_pipeline) if bd_ok == EstadoFuente.OK else None,
            vistas_en_bd=len(base_viva.vistas) if base_viva else None,
        )
        p.clasificacion = _clasificar(p, vivas_ok)
        pipelines[nombre] = p

    dags_sin_pipeline = sorted(
        d for d in dags if _normalizar_dag_id(d) not in pipelines and d not in pipelines
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
        "alias_nombres": {p.alias_html: n for n, p in pipelines.items() if p.alias_html},
    }
    resumen = {
        "pipelines": len(pipelines),
        "con_html": sum(1 for p in pipelines.values() if p.documentacion_html),
        "dags_emparejados": len(dags_por_nombre),
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
