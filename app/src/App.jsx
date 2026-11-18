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
    // Retry fetching sessions with retry interval if backend is still spinning up
    const initApp = async () => {
      let retries = 10
      while (retries > 0) {
        try {
          await fetchSessions()
          if (!useJarvisStore.getState().activeSessionId) {
            await createSession()
          }
          break
        } catch (e) {
          retries--
          await new Promise((r) => setTimeout(r, 1500))
        }
      }
    }
    initApp()
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
