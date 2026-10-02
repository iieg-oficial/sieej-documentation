const BASE = (process.env.MARIACHI_URL ?? "").replace(/\/$/, "");

if (process.env.MARIACHI_TLS_VERIFY === "false") process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
const RUTA = "/api/public/sieej-documentacion";
const REVISAR_VERSION_MS = 30_000;
const TIEMPO_LIMITE_MS = 5_000;

type Respuesta<T> = { estado: "ok"; datos: T } | { estado: "no_encontrado" } | { estado: "sin_api" };

let version: { token: string; revisado: number } | null = null;
const respuestas = new Map<string, { token: string; datos: unknown }>();

const pedirJson = async (ruta: string): Promise<Response> =>
  fetch(`${BASE}${RUTA}${ruta}`, {
    signal: AbortSignal.timeout(TIEMPO_LIMITE_MS),
    headers: { "User-Agent": "sieej-documentacion-web", Accept: "application/json" },
  });

async function tokenActual(): Promise<string> {
  const ahora = Date.now();
  if (version && ahora - version.revisado < REVISAR_VERSION_MS) return version.token;
  const respuesta = await pedirJson("/version");
  if (!respuesta.ok) throw new Error(`version ${respuesta.status}`);
  const { version: token } = (await respuesta.json()) as { version: string };
  version = { token, revisado: ahora };
  return token;
}

export const apiConfigurada = (): boolean => BASE.length > 0;

export async function consultar<T>(ruta: string): Promise<Respuesta<T>> {
  if (!apiConfigurada()) return { estado: "sin_api" };
  try {
    const token = await tokenActual();
    const guardada = respuestas.get(ruta);
    if (guardada && guardada.token === token) return { estado: "ok", datos: guardada.datos as T };
    const respuesta = await pedirJson(ruta);
    if (respuesta.status === 404) return { estado: "no_encontrado" };
    if (!respuesta.ok) throw new Error(`${ruta} ${respuesta.status}`);
    const datos = (await respuesta.json()) as T;
    respuestas.set(ruta, { token, datos });
    return { estado: "ok", datos };
  } catch {
    const guardada = respuestas.get(ruta);
    return guardada ? { estado: "ok", datos: guardada.datos as T } : { estado: "sin_api" };
  }
}

export async function enviarEventos(lote: unknown, uaVisitante: string): Promise<void> {
  const clave = process.env.MARIACHI_SYNC_KEY;
  if (!apiConfigurada() || !clave) return;
  try {
    await fetch(`${BASE}${RUTA}/eventos/lote`, {
      method: "POST",
      signal: AbortSignal.timeout(TIEMPO_LIMITE_MS),
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": clave,
        "User-Agent": "sieej-documentacion-web",
        "X-Visitante-UA": uaVisitante.slice(0, 300),
      },
      body: JSON.stringify(lote),
    });
  } catch {
    return;
  }
}
