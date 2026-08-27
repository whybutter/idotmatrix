import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// Build a single self-contained IIFE bundle with React inlined,
// output to dist/idotmatrix-panel.js. This is loaded by Home Assistant
// as a custom panel module which mounts <idotmatrix-panel>.
export default defineConfig({
  plugins: [react()],
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    target: "es2020",
    minify: "esbuild",
    cssCodeSplit: false,
    lib: {
      entry: resolve(__dirname, "src/main.tsx"),
      name: "IDotMatrixPanel",
      formats: ["iife"],
      fileName: () => "idotmatrix-panel.js",
    },
    rollupOptions: {
      output: {
        // Everything inlined into the single JS file. CSS is injected at
        // runtime by the entry, so we don't emit a separate stylesheet.
        inlineDynamicImports: true,
        entryFileNames: "idotmatrix-panel.js",
        assetFileNames: "idotmatrix-panel.[ext]",
      },
    },
  },
});
