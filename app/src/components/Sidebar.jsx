import React from 'react'
import { MessageSquare, LayoutDashboard, Database, Settings, Plus, Trash2, ChevronLeft, ChevronRight, Mic, Sparkles, CheckSquare } from 'lucide-react'
import useJarvisStore from '../store/useJarvisStore'

export default function Sidebar() {
  const {
    sidebarCollapsed,
    toggleSidebar,
    activeTab,
    setActiveTab,
    sessions,
    activeSessionId,
    loadSession,
    createSession,
    deleteSession
  } = useJarvisStore()

  const tabs = [
    { id: 'chat', icon: MessageSquare, label: 'Chat' },
    { id: 'voice', icon: Mic, label: 'Voice Chat' },
    { id: 'imagegen', icon: Sparkles, label: 'Image Gen' },
    { id: 'tasks', icon: CheckSquare, label: 'Task Center' },
    { id: 'hud', icon: LayoutDashboard, label: 'HUD Dashboard' },
    { id: 'memory', icon: Database, label: '4-Tier Memory' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ]

  return (
    <aside className="relative flex flex-col h-full transition-all duration-300"
           style={{
             width: sidebarCollapsed ? '64px' : '260px',
             background: 'var(--bg-secondary)',
             borderRight: '1px solid var(--border)',
           }}>
      
      {/* Tab Navigation */}
      <div className="flex flex-col gap-1 p-3 mt-1"
           style={{ borderBottom: '1px solid var(--border)' }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm font-medium"
            style={{
              background: activeTab === tab.id ? 'var(--accent-glow)' : 'transparent',
              color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-secondary)',
            }}
            title={sidebarCollapsed ? tab.label : undefined}
          >
            <tab.icon size={18} style={{ minWidth: '18px' }} />
            {!sidebarCollapsed && <span>{tab.label}</span>}
          </button>
        ))}
      </div>

      {/* Sessions List */}
      {!sidebarCollapsed && activeTab === 'chat' && (
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-xs font-bold uppercase tracking-widest"
                  style={{ color: 'var(--text-tertiary)' }}>
              Conversations
            </span>
            <button 
              onClick={() => createSession()}
              className="p-1 rounded transition-colors"
              style={{ color: 'var(--accent)', background: 'var(--accent-glow)' }}
            >
              <Plus size={14} />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
            {sessions.map(session => (
              <div 
                key={session.session_id}
                onClick={() => loadSession(session.session_id)}
                className="group flex items-center justify-between px-3 py-2 rounded-md cursor-pointer transition-colors text-sm"
                style={{
                  background: activeSessionId === session.session_id ? 'var(--bg-hover)' : 'transparent',
                  color: activeSessionId === session.session_id ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                <div className="truncate font-medium pr-2">
                  {session.title || 'New conversation'}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteSession(session.session_id); }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ color: 'var(--red)' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Collapse Toggle */}
      <button 
        onClick={toggleSidebar}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-12 rounded-full flex items-center justify-center z-10 transition-colors"
        style={{
          background: 'var(--bg-tertiary)',
          border: '1px solid var(--border)',
          color: 'var(--text-secondary)',
        }}
      >
        {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  )
}
