import type { APIRoute } from "astro";
import { stat } from "node:fs/promises";
import { join } from "node:path";
import paquete from "../../package.json";

const DIRECTORIO = process.env.DATA_DIR ?? join(process.cwd(), "..", "data");
const BASE = (process.env.MARIACHI_URL ?? "").replace(/\/$/, "");
const HORAS_LIMITE = 26;
const ARRANQUE = new Date().toISOString();

type Check = { status: "ok" | "degraded" | "down"; [clave: string]: unknown };

async function datos(): Promise<Check> {
  try {
    const { mtime } = await stat(join(DIRECTORIO, ".ultima-corrida"));
    const horas = (Date.now() - mtime.getTime()) / 3_600_000;
    return { status: horas <= HORAS_LIMITE ? "ok" : "degraded", ultima_corrida: mtime.toISOString(), horas: Math.round(horas * 10) / 10 };
  } catch {
    return { status: "degraded", detalle: "el sincronizador no ha corrido" };
  }
}

async function mariachi(): Promise<Check> {
  if (!BASE) return { status: "degraded", detalle: "MARIACHI_URL sin configurar" };
  try {
    const respuesta = await fetch(`${BASE}/api/public/sieej-documentacion/salud`, { signal: AbortSignal.timeout(3_000) });
    if (!respuesta.ok) return { status: "down", http: respuesta.status };
    const salud = (await respuesta.json()) as { estado: string; horas_desde_ultima: number | null; pipelines_publicados: number };
    return {
      status: salud.estado === "ok" ? "ok" : "degraded",
      sincronizacion: salud.estado,
      horas_desde_ultima: salud.horas_desde_ultima,
      pipelines_publicados: salud.pipelines_publicados,
    };
  } catch (error) {
    return { status: "down", detalle: String(error) };
  }
}

export const GET: APIRoute = async () => {
  const checks = { datos: await datos(), mariachi: await mariachi() };
  const estados = Object.values(checks).map((c) => c.status);
  const status = estados.includes("down") ? "degraded" : estados.every((e) => e === "ok") ? "ok" : "degraded";
  return new Response(
    JSON.stringify({ service: "sieej-documentation", version: paquete.version, deployed_at: ARRANQUE, status, checks }),
    { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } },
  );
};
