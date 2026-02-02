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
      },
      '/war-media': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true
      }
    }
  },
  root: './',
  // Use /haven-ui/ base in production builds so the app works when mounted at /haven-ui
  base: process.env.NODE_ENV === 'production' ? '/haven-ui/' : '/',
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['favicon.svg', 'icon.svg'],
    workbox: {
      maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
      // Don't precache lazy-loaded chunks - they'll be cached on-demand
      // This prevents the initial burst of requests for all JS files
      globPatterns: ['**/*.{html,css}', 'assets/index-*.js', 'assets/vendor-react-*.js', 'assets/vendor-ui-*.js'],
    },
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
    rollupOptions: {
      output: {
        // Code splitting for better caching and faster initial load
        manualChunks: {
          // Core React - rarely changes, cache separately
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Three.js and related - only loaded when War Room is visited
          'vendor-three': ['three', '@react-three/fiber', '@react-three/drei'],
          // UI utilities
          'vendor-ui': ['axios', '@heroicons/react'],
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  }
})
