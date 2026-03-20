import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  // Load .env from parent directory (root of project)
  envDir: resolve(__dirname, '..'),
  envPrefix: 'VITE_',
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://localhost:8001',
    },
  },
});
