import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served at the domain root (its own domain via NPM), so base = '/'.
// In dev, `npm run dev` proxies /api to the FastAPI backend on :8090.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8090',
    },
  },
})
