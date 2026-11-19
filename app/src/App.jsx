import React, { useEffect } from 'react'
import Sidebar from './components/Sidebar'
import TitleBar from './components/TitleBar'
import CommandCenter from './components/CommandCenter'
import ChatView from './components/ChatView'
import VoiceView from './components/VoiceView'
import ImageGenView from './components/ImageGenView'
import TaskView from './components/TaskView'
import HUDView from './components/HUDView'
import MemoryView from './components/MemoryView'
import SettingsView from './components/SettingsView'

import useJarvisStore from './store/useJarvisStore'
import useWebSocket from './hooks/useWebSocket'

export default function App() {
  const { 
    activeTab, 
    activeSessionId, 
    fetchSessions, 
    createSession,
    theme 
  } = useJarvisStore()

  useWebSocket(activeSessionId)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    // Smart backend discovery: ping health endpoint with backoff before initializing sessions
    let cancelled = false
    const initApp = async () => {
      let backoffMs = 1500
      const MAX_BACKOFF = 15000
      let retries = 10

      // Phase 1: Wait for backend to respond
      while (retries > 0 && !cancelled) {
        try {
          const ctrl = new AbortController()
          const id = setTimeout(() => ctrl.abort(), 2000)
          const res = await fetch('http://localhost:8080/api/system/status', { signal: ctrl.signal })
          clearTimeout(id)
          if (res.ok) break // Backend is online
        } catch {
          // Silently wait — no console spam
        }
        retries--
        if (retries > 0) await new Promise((r) => setTimeout(r, backoffMs))
        backoffMs = Math.min(backoffMs * 1.5, MAX_BACKOFF)
      }

      if (cancelled || retries <= 0) return

      // Phase 2: Backend is online — synchronize sessions reliably without overwriting
      try {
        const existingSessions = await fetchSessions()
        // ONLY create a session if the database has absolutely 0 sessions
        if ((!existingSessions || existingSessions.length === 0) && !useJarvisStore.getState().activeSessionId) {
          await createSession()
        }
      } catch {
        // Session init failed — will retry on next user interaction
      }
    }
    initApp()
    return () => { cancelled = true }
  }, [])

  return (
    <div style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
         className="flex flex-col h-screen w-full overflow-hidden">
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 relative flex flex-col min-w-0 overflow-hidden">
          {activeTab === 'command' && <CommandCenter />}
          {activeTab === 'chat' && <ChatView />}
          {activeTab === 'voice' && <VoiceView />}
          {activeTab === 'imagegen' && <ImageGenView />}
          {activeTab === 'tasks' && <TaskView />}
          {activeTab === 'hud' && <HUDView />}
          {activeTab === 'memory' && <MemoryView />}
          {activeTab === 'settings' && <SettingsView />}
        </main>
      </div>
    </div>
  )
}
