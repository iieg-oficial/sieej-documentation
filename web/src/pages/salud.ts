import type { APIRoute } from "astro";

export const GET: APIRoute = () =>
  new Response("ok\n", { headers: { "Content-Type": "text/plain", "Cache-Control": "no-store" } });
