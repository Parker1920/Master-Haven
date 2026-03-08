import React, { createContext, useEffect } from 'react'
import { setApiTagColors } from '../utils/tagColors'

export const ThemeContext = createContext(null)

function setVar(name, value){
  try{ document.documentElement.style.setProperty(name, value) }catch(e){}
}

/**
 * Fetches theme colors from /api/settings on mount and applies them as CSS custom properties on :root.
 * Also fetches discord_tag_colors from the API and populates the tagColors module cache.
 */
export default function ThemeProvider({ children }){
  useEffect(()=>{
    // Fetch discord tag colors from API and populate the tagColors cache
    fetch('/api/discord_tag_colors').then(r=>r.json()).then(data=>{
      setApiTagColors(data)
    }).catch(()=>{})

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
