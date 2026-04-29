/**
 * Application entry point. Mounts React app under /haven-ui base path.
 * Provider order: BrowserRouter -> ThemeProvider (CSS vars) -> App.
 */
import React from 'react'
import axios from 'axios'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import ThemeProvider from './components/ThemeProvider'
import './styles/index.css'

// Poster routes (/voyager/:user, /atlas/:galaxy, /poster/:type/:key) are also
// served at the bare path by the backend's SSR shim so share URLs stay clean
// (e.g. havenmap.online/voyager/hiroki-rinn). When that's how the page was
// loaded, drop the /haven-ui basename so React Router actually matches the
// route definitions in App.jsx. Asset URLs are absolute (Vite base=/haven-ui)
// so they keep loading regardless. See Haven-UI/backend/routes/ssr.py.
const POSTER_PREFIXES = ['/voyager/', '/atlas/', '/poster/']
const isPosterPath = POSTER_PREFIXES.some((p) => window.location.pathname.startsWith(p))
const routerBasename = isPosterPath ? '' : '/haven-ui'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename={routerBasename}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
)

// Ensure axios sends cookies automatically for session auth
axios.defaults.withCredentials = true
