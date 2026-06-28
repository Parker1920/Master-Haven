import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The /api proxy makes the backend same-origin in dev, so session cookies and the OAuth
// redirect (http://localhost:5173/api/auth/callback) work without cross-origin friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8090', changeOrigin: true },
    },
  },
});
