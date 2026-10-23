import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In development the frontend calls /api/... on its own origin and Vite forwards those
// requests to the FastAPI backend, so no CORS setup is needed while developing.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": env.BACKEND_URL || "http://127.0.0.1:8000",
      },
    },
  };
});
