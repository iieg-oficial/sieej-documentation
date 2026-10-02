import { readFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";

const DIRECTORIO = process.env.DATA_DIR ?? join(process.cwd(), "..", "data");
const cache = new Map<string, { mtime: number; datos: unknown }>();

export async function leerJson<T>(relativo: string): Promise<T | null> {
  const ruta = join(DIRECTORIO, relativo);
  try {
    const { mtimeMs } = await stat(ruta);
    const guardado = cache.get(ruta);
    if (guardado && guardado.mtime === mtimeMs) return guardado.datos as T;
    const datos = JSON.parse(await readFile(ruta, "utf8")) as T;
    cache.set(ruta, { mtime: mtimeMs, datos });
    return datos;
  } catch {
    return (cache.get(ruta)?.datos as T) ?? null;
  }
}

export async function listarJson(carpeta: string): Promise<string[]> {
  try {
    const nombres = await readdir(join(DIRECTORIO, carpeta));
    return nombres.filter((n) => n.endsWith(".json")).map((n) => n.slice(0, -5));
  } catch {
    return [];
  }
}
