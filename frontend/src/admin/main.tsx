import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './admin.css'
import { App } from './App'
import { AuthProvider } from './auth'

const root = document.getElementById('root')
if (!root) throw new Error('admin.html has no #root element')

createRoot(root).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
)
