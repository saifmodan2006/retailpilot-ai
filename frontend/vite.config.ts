import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {rollupOptions: {output: {manualChunks: {
    charts: ["recharts"], forms: ["react-hook-form", "zod", "@hookform/resolvers"],
    react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"],
  }}}},
  server: {
    proxy: {
      "/api": process.env.RETAILPILOT_DEV_API || "http://127.0.0.1:8000",
      "/samples": { target: process.env.RETAILPILOT_DEV_API || "http://127.0.0.1:8000" },
    },
  },
});
