import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/globals.css'
import axios from 'axios'

// Configure global Axios instance to inject Bearer token on all requests
axios.interceptors.request.use(
  (config) => {
    let token = localStorage.getItem('jarvis_auth_token') || ''
    if (!token && window.jarvisAPI?.getAuthToken) {
      token = window.jarvisAPI.getAuthToken() || ''
      if (token) localStorage.setItem('jarvis_auth_token', token)
    }
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Intercept window.fetch to automatically append Bearer token
const originalFetch = window.fetch
window.fetch = async (...args) => {
  let [resource, config] = args
  config = config || {}
  config.headers = config.headers || {}

  let token = localStorage.getItem('jarvis_auth_token') || ''
  if (!token && window.jarvisAPI?.getAuthToken) {
    token = window.jarvisAPI.getAuthToken() || ''
    if (token) localStorage.setItem('jarvis_auth_token', token)
  }

  if (token) {
    if (config.headers instanceof Headers) {
      config.headers.set('Authorization', `Bearer ${token}`)
    } else if (Array.isArray(config.headers)) {
      config.headers.push(['Authorization', `Bearer ${token}`])
    } else {
      config.headers['Authorization'] = `Bearer ${token}`
    }
  }

  return originalFetch(resource, config)
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
