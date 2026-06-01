import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true, // Remote-SSH/외부 접근 허용 (0.0.0.0 바인드)
    // dev 에서 /api 요청을 BE(:8000)로 프록시 — FE 는 상대경로만 쓰면 돼(포트 1개 포워딩),
    // CORS·이중 포트포워딩 불필요. prod 빌드는 VITE_API_BASE_URL(절대 URL)을 쓴다.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
