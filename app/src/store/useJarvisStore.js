/**
 * useJarvisStore.js — Zustand Global State
 * ==========================================
 * Centralized state for JARVIS app: sessions, messages, UI state,
 * theme/mode management, and WebSocket connection status.
 */

import { create } from 'zustand'

const API_BASE = 'http://localhost:8080'

const useJarvisStore = create((set, get) => ({
  // ── Sessions ──────────────────────────────────────────────────
  sessions: [],
  activeSessionId: null,
  messages: [],

  // ── JARVIS State ──────────────────────────────────────────────
  jarvisState: 'idle', // idle | listening | thinking | speaking | muted
  isConnected: false,
  isMuted: false,

  // ── Theme / Mode ──────────────────────────────────────────────
  // "work" (cyan), "focus" (amber), "casual" (violet)
  theme: 'work',

  // ── Streaming ─────────────────────────────────────────────────
  isStreaming: false,
  streamingContent: '',
  agentSteps: [], // List of intermediate reasoning steps
  pendingApproval: null, // { request_id, action, details }

  // ── UI ────────────────────────────────────────────────────────
  activeTab: 'command', // command | chat | voice | imagegen | hud | memory | settings
  sidebarCollapsed: false,

  // ═══════════════════════════════════════════════════════════════
  // ACTIONS
  // ═══════════════════════════════════════════════════════════════

  setActiveTab: (tab) => set({ activeTab: tab }),
  setJarvisState: (state) => set({ jarvisState: state }),
  setConnected: (v) => set({ isConnected: v }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  // ── Theme / Mode ──────────────────────────────────────────────
  setTheme: (theme) => {
    document.documentElement.setAttribute('data-theme', theme)
    set({ theme })
    // Persist to backend
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme }),
    }).catch(() => {})
  },

  // ── Sessions ──────────────────────────────────────────────────
  fetchSessions: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions`)
      const data = await res.json()
      set({ sessions: data })
    } catch {
      console.error('Failed to fetch sessions')
    }
  },

  createSession: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New conversation' }),
      })
      const data = await res.json()
      set((s) => ({
        sessions: [
          {
            session_id: data.session_id,
            title: data.title,
            message_count: 0,
            last_message: '',
            created_at: data.created_at,
          },
          ...s.sessions,
        ],
        activeSessionId: data.session_id,
        messages: [],
      }))
      return data.session_id
    } catch {
      console.error('Failed to create session')
      return null
    }
  },

  loadSession: async (sessionId) => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`)
      const data = await res.json()
      set({
        activeSessionId: sessionId,
        messages: data.messages || [],
      })
    } catch {
      console.error('Failed to load session')
    }
  },

  deleteSession: async (sessionId) => {
    try {
      await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: 'DELETE',
      })
      const state = get()
      set({
        sessions: state.sessions.filter((s) => s.session_id !== sessionId),
        ...(state.activeSessionId === sessionId
          ? { activeSessionId: null, messages: [] }
          : {}),
      })
    } catch {
      console.error('Failed to delete session')
    }
  },

  // ── Messaging ─────────────────────────────────────────────────
  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  setStreaming: (v) => set({ isStreaming: v }),

  appendStreamToken: (token) =>
    set((s) => ({ streamingContent: s.streamingContent + token })),

  addAgentStep: (step) =>
    set((s) => ({ agentSteps: [...s.agentSteps, step] })),

  clearAgentSteps: () =>
    set({ agentSteps: [] }),

  setPendingApproval: (approval) =>
    set({ pendingApproval: approval }),

  resolveApproval: async (requestId, approved) => {
    try {
      await fetch(`${API_BASE}/api/security/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId, approved }),
      })
      set({ pendingApproval: null })
    } catch (e) {
      console.error('Failed to resolve approval:', e)
    }
  },

  resetStream: () => set({ streamingContent: '', isStreaming: false, agentSteps: [] }),

  // ── Update session title (from WS title_update) ───────────────
  updateSessionTitle: (sessionId, title) =>
    set((s) => ({
      sessions: s.sessions.map((sess) =>
        sess.session_id === sessionId ? { ...sess, title } : sess
      ),
    })),
}))

export default useJarvisStore
