// @ts-check
import { defineConfig } from "astro/config";
import node from "@astrojs/node";

export default defineConfig({
  site: process.env.SITE_URL || "https://iieg.jalisco.gob.mx",
  output: "server",
  adapter: node({ mode: "standalone" }),
  trailingSlash: "ignore",
});
