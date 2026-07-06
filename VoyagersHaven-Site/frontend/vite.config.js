import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served at the domain root (its own domain via NPM), so base = '/'.
// In dev, `npm run dev` proxies /api to the FastAPI backend on :8090.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,            // bind 0.0.0.0 so it's reachable over the LAN/Tailscale
    allowedHosts: true,    // dev server only ever runs on a private tailnet
    proxy: {
      '/api': 'http://localhost:8090',
    },
  },
})
