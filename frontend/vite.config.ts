import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El backend vive en :8000. El proxy evita que la lectura necesite CORS en desarrollo,
// que es distinto de la lista explícita de orígenes que exige RC-08 en producción.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
