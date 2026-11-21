/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const BACKEND = process.env.DREAMGUARD_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig(({ command }) => ({
  // The production build is served by the backend under /dashboard/.
  base: command === "build" ? "/dashboard/" : "/",
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        // Separate, long-cached vendor chunks instead of one large bundle.
        codeSplitting: {
          groups: [
            {
              name: "charts",
              test: /node_modules[\\/](recharts|d3-|victory-vendor|@reduxjs|immer|reselect)/,
            },
            { name: "react", test: /node_modules[\\/](react|react-dom|scheduler|@tanstack)[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: false },
      "/ws": { target: BACKEND, ws: true, changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
}));
