import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Bare local dev: `npm run dev` on :5173 proxies API calls to the backend.
    // In the container there is no proxy — FastAPI serves the built bundle
    // and the API from one origin.
    proxy: { '/api': 'http://localhost:8090' },
  },
})
