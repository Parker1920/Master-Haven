import { Route, Routes } from 'react-router-dom'
import Nav from './components/Nav'
import Footer from './components/Footer'
import ScrollToTop from './components/ScrollToTop'
import { ToastProvider } from './components/Toast'
import Home from './pages/Home'
import Work from './pages/Work'
import Hosting from './pages/Hosting'
import About from './pages/About'
import Support from './pages/Support'
import Contact from './pages/Contact'
import Admin from './pages/Admin'
import Success from './pages/Success'
import NotFound from './pages/NotFound'
import { Privacy, Terms } from './pages/Legal'

export default function App() {
  return (
    <ToastProvider>
      <ScrollToTop />
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/work" element={<Work />} />
          <Route path="/hosting" element={<Hosting />} />
          <Route path="/about" element={<About />} />
          <Route path="/support" element={<Support />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/success" element={<Success />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </ToastProvider>
  )
}
