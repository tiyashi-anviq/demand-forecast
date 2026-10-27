import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev the UI talks to the FastAPI server on :8000 through this proxy (override with VITE_API_TARGET).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': process.env.VITE_API_TARGET || 'http://127.0.0.1:8000' },
  },
  preview: { port: 4173, proxy: { '/api': process.env.VITE_API_TARGET || 'http://127.0.0.1:8000' } },
});
