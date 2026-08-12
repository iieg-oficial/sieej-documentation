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
    registros: int | None = None
    columnas: list[Columna] = Field(default_factory=list)
    en_bd: bool | None = None  # None = BD no consultada
    en_docs: bool = False
    solo_en_bd: bool = False
    solo_en_docs: bool = False
    archivo_md: str | None = None


class BaseDeDatos(BaseModel):
    nombre: str
    es_infraestructura: bool = False
    vistas: list[Vista] = Field(default_factory=list)


class CorridasRecientes(BaseModel):
    total: int = 0
    exitos: int = 0
    fallos: int = 0


class Dag(BaseModel):
    dag_id: str
    pausado: bool | None = None
    ultima_corrida_fecha: datetime | None = None
    ultima_corrida_estado: str | None = None
    corridas_recientes: CorridasRecientes | None = None


class DocumentacionHtml(BaseModel):
    archivo: str
    titulo: str


class ClasificacionPipeline(str, Enum):
    DOCUMENTADO = "documentado"
    DOCUMENTACION_PENDIENTE = "documentacion_pendiente"
    POSIBLE_DESACTUALIZADO = "posible_desactualizado"
    SIN_VERIFICAR = "sin_verificar"  # fuentes vivas no disponibles aún


class Pipeline(BaseModel):
    nombre: str
    documentacion_html: DocumentacionHtml | None = None
    alias_html: str | None = None
    vistas_documentadas: list[str] = Field(default_factory=list)
    dag: Dag | None = None
    bd_existe: bool | None = None
    vistas_en_bd: int | None = None
    clasificacion: ClasificacionPipeline = ClasificacionPipeline.SIN_VERIFICAR


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
