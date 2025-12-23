import React from 'react'
import axios from 'axios'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import ThemeProvider from './components/ThemeProvider'
import { InactivityProvider } from './utils/InactivityContext'
import './styles/index.css'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename="/haven-ui">
      <ThemeProvider>
        <InactivityProvider timeout={3600000}>
          <App />
        </InactivityProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
)

// Ensure axios sends cookies automatically for session auth
axios.defaults.withCredentials = true
