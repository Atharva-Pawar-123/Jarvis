import React, { useEffect } from 'react'
import Sidebar from './components/Sidebar'
import TitleBar from './components/TitleBar'
import ChatView from './components/ChatView'
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
    fetchSessions().then(() => {
      if (!useJarvisStore.getState().activeSessionId) {
        createSession()
      }
    })
  }, [])

  return (
    <div style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
         className="flex flex-col h-screen w-full overflow-hidden">
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 relative flex flex-col min-w-0 overflow-hidden">
          {activeTab === 'chat' && <ChatView />}
          {activeTab === 'hud' && <HUDView />}
          {activeTab === 'memory' && <MemoryView />}
          {activeTab === 'settings' && <SettingsView />}
        </main>
      </div>
    </div>
  )
}
