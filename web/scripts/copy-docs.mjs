/**
 * Copia la documentación HTML de pipelines (generada fuera de este repo)
 * a public/docs/ para servirla tal cual dentro del sitio.
 *
 * Origen: DOCS_HTML_DIR (variable de entorno). Absorbe archivos nuevos sin
 * cambios de código (copia todo el directorio). Si el origen no está
 * disponible degrada con gracia: conserva la copia previa si existe y avisa,
 * pero nunca rompe el build.
 */
import {
  chmodSync,
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
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

// Copia limpia: se vacía el destino para no arrastrar archivos que ya no
// existen en el origen (la degradación de arriba solo aplica si el origen
// no está disponible).
rmSync(destino, { recursive: true, force: true });
mkdirSync(destino, { recursive: true });

// Sin archivos/directorios ocultos (p. ej. .claude/) y sin el index.html:
// el catálogo de la landing reemplaza al índice de pipelines.
cpSync(origenAbs, destino, {
  recursive: true,
  filter: (src) => !basename(src).startsWith(".") && basename(src) !== "index.html",
});

// Permisos legibles para el servidor web, sin importar los modos del origen.
const normalizar = (ruta) => {
  const info = statSync(ruta);
  if (info.isDirectory()) {
    chmodSync(ruta, 0o755);
    for (const entrada of readdirSync(ruta)) normalizar(join(ruta, entrada));
  } else {
    chmodSync(ruta, 0o644);
  }
};
normalizar(destino);

// Homologación tipográfica con la landing (identidad IIEG): los documentos
// declaran 'Segoe UI'/'JetBrains Mono' pero no incrustan fuentes. Se inyecta
// un bloque marcado que carga las webfonts del sitio (/fonts/) y unifica el
// cuerpo en Poppins. La inyección es idempotente y se rehace en cada copia.
const ESTILO_MARCA = 'data-inyectado="sieej-landing"';
const ESTILO_FUENTES = `<style ${ESTILO_MARCA}>
@font-face{font-family:'Poppins';font-style:normal;font-weight:400;font-display:swap;src:url('/fonts/poppins-400.woff2') format('woff2')}
@font-face{font-family:'Poppins';font-style:normal;font-weight:600;font-display:swap;src:url('/fonts/poppins-600.woff2') format('woff2')}
@font-face{font-family:'Poppins';font-style:normal;font-weight:700;font-display:swap;src:url('/fonts/poppins-700.woff2') format('woff2')}
@font-face{font-family:'JetBrains Mono';font-style:normal;font-weight:400;font-display:swap;src:url('/fonts/jetbrains-mono-400.woff2') format('woff2')}
@font-face{font-family:'JetBrains Mono';font-style:normal;font-weight:600;font-display:swap;src:url('/fonts/jetbrains-mono-600.woff2') format('woff2')}
body{font-family:'Poppins',Arial,'Segoe UI',sans-serif}
</style>`;

const inyectarFuentes = (ruta) => {
  for (const entrada of readdirSync(ruta)) {
    const rutaEntrada = join(ruta, entrada);
    if (statSync(rutaEntrada).isDirectory()) {
      inyectarFuentes(rutaEntrada);
    } else if (entrada.endsWith(".html")) {
      const contenido = readFileSync(rutaEntrada, "utf-8");
      if (!contenido.includes(ESTILO_MARCA) && contenido.includes("</head>")) {
        writeFileSync(rutaEntrada, contenido.replace("</head>", `${ESTILO_FUENTES}\n</head>`));
      }
    }
  }
};
inyectarFuentes(destino);

const html = readdirSync(destino).filter((f) => f.endsWith(".html")).length;
console.log(`[copy-docs] ${html} documentos HTML copiados a ${join("public", "docs")}.`);
