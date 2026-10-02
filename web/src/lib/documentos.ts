import { leerJson } from "./datos";
import { consultar } from "./mariachi";

type Columna = { posicion: number; nombre: string; tipo: string; nullable?: boolean; descripcion: string | null };
type Tabla = { nombre: string; descripcion: string | null; filas: number | null; columnas: { nombre: string; tipo: string; pk: boolean; nullable: boolean }[] };
type Vista = { esquema?: string; nombre: string; tipo?: string; descripcion: string | null; registros: number | null; columnas: Columna[] };

export type Base = {
  nombre: string;
  tablas: Tabla[];
  relaciones: { tabla: string; columnas: string[]; ref_tabla: string; ref_columnas: string[] }[];
  vistas: Vista[];
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

export type Seccion = { id: string; tipo: string; titulo: string; contenido: Record<string, any> };

export type Documento = {
  clave: string;
  titulo: string;
  producto: string;
  clasificacion: string | null;
  secciones: Seccion[];
  base: Base | null;
  origen_base: string | null;
  corte_respaldo: string | null;
  etapas: Etapa[];
  der_svg: string | null;
};

export type Resumen = {
  clave: string;
  titulo: string;
  producto: string;
  clasificacion: string | null;
  etapas: Etapa[];
  vistasEnBd: number | null;
  vistasDocumentadas: number;
};

type PipelineInventario = {
  nombre: string;
  documento: { titulo: string; producto: string } | null;
  vistas_documentadas: string[];
  vistas_en_bd: number | null;
  etapas: Etapa[];
  clasificacion: string;
};

type Inventario = { generado: string; resumen: Record<string, unknown>; pipelines: Record<string, PipelineInventario> };

const porTitulo = (a: { titulo: string }, b: { titulo: string }) => a.titulo.localeCompare(b.titulo, "es");

export const leerInventario = () => leerJson<Inventario>("inventario.json");

export async function listarPipelines(): Promise<Resumen[]> {
  const api = await consultar<any[]>("/pipelines");
  if (api.estado === "ok") {
    return api.datos
      .map((p) => ({
        clave: p.clave,
        titulo: p.titulo,
        producto: p.producto,
        clasificacion: p.clasificacion,
        etapas: p.etapas ?? [],
        vistasEnBd: p.vistas_en_bd,
        vistasDocumentadas: p.vistas_documentadas,
      }))
      .sort(porTitulo);
  }
  const inventario = await leerInventario();
  return Object.values(inventario?.pipelines ?? {})
    .map((p) => ({
      clave: p.nombre,
      titulo: p.documento?.titulo ?? p.nombre.replaceAll("_", " "),
      producto: p.documento?.producto ?? "",
      clasificacion: p.clasificacion,
      etapas: p.etapas ?? [],
      vistasEnBd: p.vistas_en_bd,
      vistasDocumentadas: p.vistas_documentadas.length,
    }))
    .sort(porTitulo);
}

const seccion = (tipo: string, titulo: string, contenido: Record<string, any>): Seccion => ({
  id: tipo,
  tipo,
  titulo,
  contenido,
});

function desdeLocal(p: any, etapasInventario: Etapa[]): Documento {
  const doc = p.documento;
  const secciones: Seccion[] = [];
  if (doc?.descripcion?.length) {
    secciones.push(seccion("descripcion", "Descripción", { parrafos: doc.descripcion, avisos: doc.avisos }));
  }
  if (doc) {
    secciones.push(seccion("fuente", "Fuente de datos", {
      caracteristicas: doc.caracteristicas, fuente_general: doc.fuente_general, descargas: doc.descargas,
    }));
  }
  secciones.push(seccion("tablas", "Tablas", { notas: {} }));
  secciones.push(seccion("vistas", "Vistas", { notas: {} }));
  secciones.push(seccion("ejecucion", "Ejecución en Airflow", { nota: null }));
  if (doc?.variables?.length) secciones.push(seccion("variables", "Variables de entorno", { variables: doc.variables }));
  secciones.push(seccion("diagrama", "Diagrama entidad-relación", { origen: "auto" }));
  return {
    clave: p.nombre,
    titulo: doc?.titulo ?? p.nombre.replaceAll("_", " "),
    producto: doc?.producto ?? "",
    clasificacion: p.clasificacion,
    secciones,
    base: p.base,
    origen_base: p.origen_base,
    corte_respaldo: p.corte_respaldo,
    etapas: p.etapas?.length ? p.etapas : etapasInventario,
    der_svg: p.der_svg,
  };
}

export async function obtenerDocumento(clave: string): Promise<Documento | null> {
  const api = await consultar<Documento>(`/pipelines/${encodeURIComponent(clave)}`);
  if (api.estado === "ok") return api.datos;
  if (api.estado === "no_encontrado") return null;
  const local = await leerJson<any>(`pipelines/${clave}.json`);
  if (!local) return null;
  const inventario = await leerInventario();
  return desdeLocal(local, inventario?.pipelines?.[clave]?.etapas ?? []);
}

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
