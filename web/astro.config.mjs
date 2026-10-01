// @ts-check
import { defineConfig } from "astro/config";

// Sitio estático: los datos entran en build desde ../data/ (generados por
// sieej_datalayer), incluidas las páginas de cada pipeline en ../data/pipelines/.
export default defineConfig({
  site: process.env.SITE_URL || "https://iieg.jalisco.gob.mx",
  base: process.env.BASE_PATH || "/",
  output: "static",
  vite: {
    server: {
      fs: {
        // Permite importar ../data/*.json (fuera de la raíz de Astro) en dev.
        allow: [".."],
      },
    },
  },
});
