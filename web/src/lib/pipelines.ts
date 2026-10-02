import inventario from "../../../data/inventario.json";

// Una página por pipeline, generada por el datalayer en data/pipelines/*.json.
const archivos = import.meta.glob("../../../data/pipelines/*.json", { eager: true, import: "default" });

export type Pagina = {
  nombre: string;
  clasificacion: string;
  documento: {
    titulo: string;
    producto: string;
    descripcion: string[];
    avisos: string[];
    caracteristicas: { etiqueta: string; valor: string }[];
    fuente_general: string | null;
    descargas: { variable: string; url: string }[];
    variables: { etiqueta: string; valor: string }[];
    commit: string | null;
  } | null;
  base: {
    nombre: string;
    tablas: { nombre: string; descripcion: string | null; filas: number | null; columnas: { nombre: string; tipo: string; pk: boolean; nullable: boolean }[] }[];
    relaciones: { tabla: string; columnas: string[]; ref_tabla: string; ref_columnas: string[] }[];
    vistas: { esquema: string; nombre: string; tipo: string; descripcion: string | null; registros: number | null; columnas: { posicion: number; nombre: string; tipo: string; nullable: boolean; descripcion: string | null }[] }[];
  } | null;
  origen_base: "bd" | "respaldo" | null;
  corte_respaldo: string | null;
  der_svg: string | null;
  etapas: Etapa[];
  generado: string;
  fuentes: Record<string, { estado: string; consultado_en: string | null }>;
};

export type Etapa = {
  dag_id: string;
  etapa: string | null;
  pausado: boolean | null;
  ultima_corrida_fecha: string | null;
  ultima_corrida_estado: string | null;
  corridas_recientes: { total: number; exitos: number; fallos: number } | null;
  descripcion?: string | null;
  programacion?: string | null;
  detalle_programacion?: string | null;
};

const titulo = (p: Pagina): string => p.documento?.titulo ?? p.nombre.replaceAll("_", " ");

export const paginas: Pagina[] = Object.values(archivos as Record<string, Pagina>)
  .map((p) => {
    const delInventario = (inventario.pipelines as Record<string, { etapas?: Etapa[] }>)[p.nombre];
    return p.etapas.length > 0 || !delInventario?.etapas ? p : { ...p, etapas: delInventario.etapas };
  })
  .sort((a, b) => titulo(a).localeCompare(titulo(b), "es"));

export const tituloDe = titulo;

export const ETAPAS: Record<string, string> = {
  bootstrap: "Carga inicial",
  update: "Actualización",
  incremental: "Carga incremental",
};

export const ESTADOS: Record<string, string> = {
  success: "correcta",
  failed: "con error",
  running: "en ejecución",
  queued: "en cola",
};

export const fecha = (iso: string | null): string | null =>
  iso
    ? new Date(iso).toLocaleDateString("es-MX", { year: "numeric", month: "long", day: "numeric" })
    : null;
