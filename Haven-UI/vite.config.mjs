import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:8005',
        ws: true
      }
    }
  },
  root: './',
  // Use /haven-ui/ base in production builds so the app works when mounted at /haven-ui
  base: process.env.NODE_ENV === 'production' ? '/haven-ui/' : '/',
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['favicon.svg', 'icon.svg', 'VH-Map.html'],
      manifest: {
      name: 'Haven Control Room',
      short_name: 'HavenCR',
        theme_color: '#00C2B3',
      start_url: process.env.NODE_ENV === 'production' ? '/haven-ui/' : '/',
      display: 'standalone',
      background_color: '#071229',
      icons: [
        { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }
      ]
    }
  })],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  }
})
