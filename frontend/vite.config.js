import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';
import { defineConfig } from 'vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 3000,
    host: '127.0.0.1',
    // Dev only: forward API calls to the Django server so the session cookie stays same-origin.
    proxy: { '/api': { target: process.env.API_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  css: { devSourcemap: false },
  build: {
    sourcemap: false, // production source maps are disabled
    minify: 'esbuild',
  },
});
