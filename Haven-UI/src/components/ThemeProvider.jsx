import React, { createContext, useEffect } from 'react'

export const ThemeContext = createContext(null)

function setVar(name, value){
  try{ document.documentElement.style.setProperty(name, value) }catch(e){}
}

export default function ThemeProvider({ children }){
  useEffect(()=>{
    // Fetch settings and apply theme CSS variables to :root
    fetch('/api/settings').then(r=>r.json()).then(j=>{
      const s = (j && j.theme) || j || {}
      const colors = s.colors || s || {}

      // Map common keys to --app-* variables used by CSS
      const bg = colors.bg_dark || colors.bg || s.bg || s.background
      const card = colors.bg_card || colors.card || s.card
      const primary = colors.accent_cyan || colors.accent || s.primary || s.accent_cyan
      const text = colors.text_primary || colors.text || s.text
      const glow = colors.glow || s.glow

      if(bg) setVar('--app-bg', bg)
      if(text) setVar('--app-text', text)
      if(card) setVar('--app-card', card)
      if(primary) setVar('--app-primary', primary)
      if(glow) setVar('--app-glow', glow)

      // Set any other color keys as --app-<key>
      const source = colors && Object.keys(colors).length ? colors : s
      Object.entries(source).forEach(([k,v])=>{
        if(!v) return
        const name = `--app-${k.replace(/_/g,'-')}`
        setVar(name, v)
      })

    }).catch(()=>{})
  }, [])

  return (
    <ThemeContext.Provider value={null}>
      {children}
    </ThemeContext.Provider>
  )
}
