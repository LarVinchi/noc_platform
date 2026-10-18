import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './index.css'

const Root = import.meta.env.DEV && /^\/demo(?:\/|$)/.test(window.location.pathname)
  ? (await import('./demo/DemoApp.jsx')).default
  : App;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
