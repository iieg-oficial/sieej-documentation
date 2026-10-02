import type { APIRoute } from "astro";

const ALIAS: Record<string, string> = { censos_economicos: "censo_economico" };

export const GET: APIRoute = ({ params, redirect }) => {
  const ruta = params.ruta ?? "";
  const nombre = ruta.match(/^([a-z0-9_]+)\.html$/)?.[1];
  if (!nombre || nombre === "index") return redirect("/#catalogo", 301);
  return redirect(`/pipelines/${ALIAS[nombre] ?? nombre}/`, 301);
};
