import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Production build is written to ../dist and served by the FastAPI backend (python run.py).
// During `npm run dev` the /api routes are proxied to the backend on port 8000.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../dist', emptyOutDir: true, chunkSizeWarningLimit: 1000, sourcemap: false },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
});
