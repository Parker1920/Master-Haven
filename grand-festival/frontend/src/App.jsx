import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import Footer from './components/Footer.jsx'
import Main from './pages/Main.jsx'
import About from './pages/About.jsx'
import Lore from './pages/Lore.jsx'
import WhosGoing from './pages/WhosGoing.jsx'
import SubmitCiv from './pages/SubmitCiv.jsx'
import SignUp from './pages/SignUp.jsx'
import Admin from './pages/Admin.jsx'

// Smooth scroll-to-top on every route change (mockup did this in showPage()).
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <Nav />
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Main />} />
        <Route path="/about" element={<About />} />
        <Route path="/lore" element={<Lore />} />
        <Route path="/whos-going" element={<WhosGoing />} />
        <Route path="/whos-going/submit" element={<SubmitCiv />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Main />} />
      </Routes>
      <Footer />
    </>
  )
}
