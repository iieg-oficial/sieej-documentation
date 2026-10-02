import { createHash } from "node:crypto";
import { defineMiddleware } from "astro:middleware";
import { enviarEventos } from "./lib/mariachi";

const INTERVALO_MS = 15_000;
const MAXIMO = 50;
type Evento = { eventName: string; props: Record<string, string> };
const pendientes = new Map<string, { pathname: string; referrer: string | null; ua: string; events: Evento[] }>();

const sesion = (ip: string, ua: string): string => {
  const dia = new Date().toISOString().slice(0, 10);
  const h = createHash("sha256").update(`${ip}|${ua}|${dia}`).digest("hex");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`;
};

const vaciar = () => {
  for (const [sessionId, lote] of pendientes) {
    pendientes.delete(sessionId);
    enviarEventos({ sessionId, source: "pagina", referrer: lote.referrer, pathname: lote.pathname, events: lote.events }, lote.ua);
  }
};

setInterval(vaciar, INTERVALO_MS).unref();

export const onRequest = defineMiddleware(async (contexto, siguiente) => {
  const respuesta = await siguiente();
  const { pathname } = contexto.url;
  const esPagina = contexto.request.method === "GET" && respuesta.status === 200
    && (respuesta.headers.get("content-type") ?? "").includes("text/html");
  if (!esPagina) return respuesta;
  const encabezados = contexto.request.headers;
  const ip = encabezados.get("x-forwarded-for")?.split(",")[0].trim() ?? encabezados.get("x-real-ip") ?? "";
  const ua = encabezados.get("user-agent") ?? "";
  const clave = pathname.match(/^\/pipelines\/([a-z0-9_]+)/)?.[1];
  const id = sesion(ip, ua);
  const lote = pendientes.get(id) ?? { pathname, referrer: encabezados.get("referer"), ua, events: [] };
  lote.events.push({ eventName: "page_view", props: { ruta: pathname, ...(clave ? { clave } : {}) } });
  pendientes.set(id, lote);
  if ([...pendientes.values()].reduce((n, l) => n + l.events.length, 0) >= MAXIMO) vaciar();
  return respuesta;
});
