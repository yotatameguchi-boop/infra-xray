import { defineConfig } from "vite";
export default defineConfig({
  build: { outDir: "../infra_xray/static", emptyOutDir: true },
  server: { host: "127.0.0.1" },
});
