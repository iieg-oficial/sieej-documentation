"""Modelos Pydantic del contrato de datos (data/*.json) que consume el sitio."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EstadoFuente(str, Enum):
    OK = "ok"
    CAIDA = "caida"
    SIN_CONFIGURAR = "sin_configurar"


class Fuente(BaseModel):
    """Estado de una fuente consultada (Airflow, BD, documentación estática)."""

    estado: EstadoFuente
    detalle: str | None = None
    consultado_en: datetime | None = None


class Columna(BaseModel):
    posicion: int
    nombre: str
    tipo: str
    nullable: bool = True
    descripcion: str | None = None
    origen_descripcion: str | None = None  # "bd" (comentario) o "docs" (views-md)


class Vista(BaseModel):
    esquema: str = "public"
    nombre: str
    tipo: str = "VIEW"  # VIEW | MATERIALIZED VIEW
    descripcion: str | None = None
    registros: int | None = None
    columnas: list[Columna] = Field(default_factory=list)
    en_bd: bool | None = None  # None = BD no consultada
    en_docs: bool = False
    solo_en_bd: bool = False
    solo_en_docs: bool = False
    archivo_md: str | None = None


class ColumnaTabla(BaseModel):
    nombre: str
    tipo: str
    pk: bool = False
    nullable: bool = True


class Tabla(BaseModel):
    nombre: str
    descripcion: str | None = None
    filas: int | None = None
    columnas: list[ColumnaTabla] = Field(default_factory=list)


class Relacion(BaseModel):
    """Llave foránea declarada en la BD: es la arista del diagrama entidad-relación."""

    tabla: str
    columnas: list[str]
    ref_tabla: str
    ref_columnas: list[str]


class BaseDeDatos(BaseModel):
    nombre: str
    es_infraestructura: bool = False
    vistas: list[Vista] = Field(default_factory=list)
    tablas: list[Tabla] = Field(default_factory=list)
    relaciones: list[Relacion] = Field(default_factory=list)


class CorridasRecientes(BaseModel):
    total: int = 0
    exitos: int = 0
    fallos: int = 0


class Dag(BaseModel):
    dag_id: str
    # Etapa del pipeline que ejecuta este DAG: bootstrap, update, incremental…
    # None cuando el DAG no lleva sufijo de etapa (pipeline de una sola pieza).
    etapa: str | None = None
    pausado: bool | None = None
    ultima_corrida_fecha: datetime | None = None
    ultima_corrida_estado: str | None = None
    corridas_recientes: CorridasRecientes | None = None
    descripcion: str | None = None
    programacion: str | None = None
    detalle_programacion: str | None = None


class Par(BaseModel):
    etiqueta: str
    valor: str


class Descarga(BaseModel):
    variable: str
    url: str


class DocumentoPipeline(BaseModel):
    """Lo que el README del pipeline en ETL-SIEEJ dice de él, en markdown en línea."""

    nombre: str
    carpeta: str
    titulo: str
    producto: str
    descripcion: list[str] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)
    caracteristicas: list[Par] = Field(default_factory=list)
    fuente_general: str | None = None
    descargas: list[Descarga] = Field(default_factory=list)
    variables: list[Par] = Field(default_factory=list)
    descripcion_tablas: dict[str, str] = Field(default_factory=dict)
    alcance_vistas: dict[str, str] = Field(default_factory=dict)
    commit: str | None = None


class DocumentoRef(BaseModel):
    titulo: str
    producto: str


class ClasificacionPipeline(str, Enum):
    DOCUMENTADO = "documentado"
    DOCUMENTACION_PENDIENTE = "documentacion_pendiente"
    POSIBLE_DESACTUALIZADO = "posible_desactualizado"
    SIN_VERIFICAR = "sin_verificar"  # fuentes vivas no disponibles aún


class Pipeline(BaseModel):
    nombre: str
    documento: DocumentoRef | None = None
    vistas_documentadas: list[str] = Field(default_factory=list)
    # Un pipeline suele ejecutarse en varias etapas (bootstrap + update), cada
    # una con su propio DAG y su propio estado: se guardan todas, no una sola.
    etapas: list[Dag] = Field(default_factory=list)
    bd_existe: bool | None = None
    vistas_en_bd: int | None = None
    clasificacion: ClasificacionPipeline = ClasificacionPipeline.SIN_VERIFICAR
    carpeta_etl: str | None = None
    fuentes_detectadas: list[str] = Field(default_factory=list)


class Inventario(BaseModel):
    generado: datetime
    datos_obsoletos: bool = False
    fuentes: dict[str, Fuente] = Field(default_factory=dict)
    resumen: dict = Field(default_factory=dict)
    cross_check: dict = Field(default_factory=dict)
    pipelines: dict[str, Pipeline] = Field(default_factory=dict)


class Numeralia(BaseModel):
    generado: datetime
    datos_obsoletos: bool = False
    fuentes: dict[str, Fuente] = Field(default_factory=dict)
    airflow: dict = Field(default_factory=dict)
    bd: dict = Field(default_factory=dict)
    documentacion: dict = Field(default_factory=dict)
    cross_check: dict = Field(default_factory=dict)


class EstructuraVistas(BaseModel):
    generado: datetime
    datos_obsoletos: bool = False
    fuentes: dict[str, Fuente] = Field(default_factory=dict)
    bases: list[BaseDeDatos] = Field(default_factory=list)


class PaginaPipeline(BaseModel):
    """Todo lo que la página `/pipelines/<nombre>/` necesita, en un solo archivo."""

    generado: datetime
    datos_obsoletos: bool = False
    fuentes: dict[str, Fuente] = Field(default_factory=dict)
    nombre: str
    clasificacion: ClasificacionPipeline = ClasificacionPipeline.SIN_VERIFICAR
    documento: DocumentoPipeline | None = None
    base: BaseDeDatos | None = None
    # "bd" cuando la base se leyó en vivo; "respaldo" cuando la BD consultada no
    # la tiene y se toma la copia de los documentos técnicos (ver respaldo/).
    origen_base: str | None = None
    corte_respaldo: str | None = None
    # erd.svg del pipeline en ETL-SIEEJ, solo cuando no hay relaciones en vivo.
    der_svg: str | None = None
    etapas: list[Dag] = Field(default_factory=list)
