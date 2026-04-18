import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import { ensureAuthenticated } from './auth/oidc'
import './styles/global.css'

async function boot() {
  await ensureAuthenticated()
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

boot().catch((e) => {
  // Any unrecoverable auth error lands here — render a minimal error state.
  document.getElementById('root')!.innerHTML =
    `<div style="padding:32px;font-family:sans-serif">Sign-in failed: ${String(e)}</div>`
})
