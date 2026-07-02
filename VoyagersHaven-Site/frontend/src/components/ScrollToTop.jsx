import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

// Reset scroll to top on every route change (multi-page feel — a fresh page,
// not a scroll position carried over from the last one).
export default function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}
