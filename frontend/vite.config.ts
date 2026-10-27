import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export const DESTINO_API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { tsconfigPaths: true },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    // Sin changeOrigin: el backend ve Host localhost:5173, el mismo origen que la cookie y que el Origin (TKT-057).
    proxy: { "/api": { target: DESTINO_API } },
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "cliente",
          environment: "jsdom",
          include: ["src/**/*.test.{ts,tsx}"],
          setupFiles: ["./src/pruebas/preparacion.ts"],
          restoreMocks: true,
        },
      },
      { extends: true, test: { name: "herramientas", environment: "node", include: ["scripts/**/*.test.ts"] } },
    ],
  },
});
