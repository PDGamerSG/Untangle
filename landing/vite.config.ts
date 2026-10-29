import { defineConfig } from "vite";

export default defineConfig({
  server: { port: 5180 },
  // three.js is most of the bundle; one chunk keeps the first paint to a single request.
  build: { target: "es2022", assetsInlineLimit: 0, chunkSizeWarningLimit: 800 },
});
