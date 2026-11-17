/**
 * api/client.js — Centralized Axios Client with Local Auth Token Injection
 * =========================================================================
 * Loads the local auth token (via Electron preload or storage) and injects
 * it as Authorization: Bearer <token> on every request.
 */

import axios from 'axios'

export const API_BASE = 'http://127.0.0.1:8080'

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Retrieve token synchronously if cached, or query preload bridge
let cachedToken = localStorage.getItem('jarvis_auth_token') || ''

export const setAuthToken = (token) => {
  cachedToken = token
  if (token) {
    localStorage.setItem('jarvis_auth_token', token)
  } else {
    localStorage.removeItem('jarvis_auth_token')
  }
}

export const getAuthToken = () => {
  if (!cachedToken && window.jarvisAPI?.getAuthToken) {
    cachedToken = window.jarvisAPI.getAuthToken() || ''
    if (cachedToken) localStorage.setItem('jarvis_auth_token', cachedToken)
  }
  return cachedToken
}

// Request interceptor attaches Bearer token
client.interceptors.request.use(
  (config) => {
    const token = getAuthToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

export default client
