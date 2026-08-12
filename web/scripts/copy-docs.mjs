/**
 * Copia la documentación HTML de pipelines (generada fuera de este repo)
 * a public/docs/ para servirla tal cual dentro del sitio.
 *
 * Origen: DOCS_HTML_DIR (variable de entorno). Absorbe archivos nuevos sin
 * cambios de código (copia todo el directorio). Si el origen no está
 * disponible degrada con gracia: conserva la copia previa si existe y avisa,
 * pero nunca rompe el build.
 */
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = dirname(fileURLToPath(import.meta.url));
const destino = resolve(raiz, "../public/docs");
const origen = process.env.DOCS_HTML_DIR;

mkdirSync(destino, { recursive: true });

if (!origen) {
  console.warn("[copy-docs] DOCS_HTML_DIR no está definida; se conserva public/docs actual.");
  process.exit(0);
}

const origenAbs = resolve(origen);
if (!existsSync(origenAbs)) {
  console.warn(`[copy-docs] No existe ${origenAbs}; se conserva public/docs actual.`);
  process.exit(0);
}

cpSync(origenAbs, destino, { recursive: true });
const html = readdirSync(destino).filter((f) => f.endsWith(".html")).length;
console.log(`[copy-docs] ${html} documentos HTML copiados a ${join("public", "docs")}.`);
