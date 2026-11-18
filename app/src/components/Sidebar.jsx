import React from 'react'
import {
  LayoutDashboard,
  Cpu,
  Bot,
  CheckSquare,
  Calendar,
  Database,
  MessageSquare,
  BookOpen,
  Wrench,
  GitBranch,
  Settings,
  Plus,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Mic,
  Sparkles,
  Flame,
  Volume2
} from 'lucide-react'
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
    deleteSession,
    jarvisState,
    setJarvisState
  } = useJarvisStore()

  // Full Navigation matrix matching Command Center reference design
  const navItems = [
    { id: 'command', icon: LayoutDashboard, label: 'Command Center' },
    { id: 'hud', icon: Cpu, label: 'AI Core' },
    { id: 'tasks', icon: Bot, label: 'Agents' },
    { id: 'tasks', icon: CheckSquare, label: 'Tasks', badge: '3' },
    { id: 'calendar', icon: Calendar, label: 'Calendar' },
    { id: 'memory', icon: Database, label: 'Memory' },
    { id: 'chat', icon: MessageSquare, label: 'Conversations', badge: sessions.length ? String(sessions.length) : '12' },
    { id: 'knowledge', icon: BookOpen, label: 'Knowledge Base' },
    { id: 'tools', icon: Wrench, label: 'Tools & Skills', badge: '18' },
    { id: 'workflows', icon: GitBranch, label: 'Workflows' },
    { id: 'imagegen', icon: Sparkles, label: 'Image Studio' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ]

  return (
    <aside
      className="relative flex flex-col h-full transition-all duration-300 border-r border-cyan-500/20 bg-[#040C18] select-none"
      style={{ width: sidebarCollapsed ? '64px' : '240px' }}
    >
      {/* Brand header in sidebar */}
      {!sidebarCollapsed && (
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-cyan-500/15">
          <div className="w-6 h-6 rounded-full border border-cyan-400 flex items-center justify-center shadow-[0_0_8px_#00c8ff]">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-xs font-black tracking-widest text-cyan-200">
              JARVIS
            </span>
            <span className="text-[8px] font-mono text-slate-400 tracking-wider">
              COMMAND CENTER
            </span>
          </div>
        </div>
      )}

      {/* Main Navigation Menu */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {navItems.map((item, idx) => {
          const isActive = activeTab === item.id
          return (
            <button
              key={idx}
              onClick={() => {
                if (item.id === 'knowledge' || item.id === 'tools' || item.id === 'workflows' || item.id === 'calendar') {
                  setActiveTab('chat')
                } else {
                  setActiveTab(item.id)
                }
              }}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-all ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-[0_0_12px_rgba(0,200,255,0.15)]'
                  : 'text-slate-400 hover:text-cyan-200 hover:bg-[#07172b]'
              }`}
              title={sidebarCollapsed ? item.label : undefined}
            >
              <div className="flex items-center gap-2.5">
                <item.icon size={16} className={isActive ? 'text-cyan-400' : 'text-slate-500'} />
                {!sidebarCollapsed && <span className="font-medium tracking-wide">{item.label}</span>}
              </div>
              {!sidebarCollapsed && item.badge && (
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-cyan-950 border border-cyan-800 text-cyan-400 font-bold">
                  {item.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Voice Status Dock at Bottom of Sidebar */}
      {!sidebarCollapsed && (
        <div className="p-3 mx-2 mb-2 rounded-xl bg-[#061426] border border-cyan-500/20 flex flex-col items-center gap-2">
          <div className="w-full flex items-center justify-between text-[10px] font-mono text-slate-400">
            <span>VOICE STATUS</span>
            <span className="text-cyan-400 font-bold">● Active</span>
          </div>

          {/* Sound wave visualizer bars */}
          <div className="flex items-center justify-center gap-1 h-5 w-full">
            <div className="w-1 bg-cyan-400 h-2 rounded-full animate-pulse" />
            <div className="w-1 bg-cyan-400 h-4 rounded-full animate-pulse delay-75" />
            <div className="w-1 bg-cyan-400 h-3 rounded-full animate-pulse delay-150" />
            <div className="w-1 bg-cyan-400 h-5 rounded-full animate-pulse delay-100" />
            <div className="w-1 bg-cyan-400 h-2 rounded-full animate-pulse delay-200" />
            <div className="w-1 bg-cyan-400 h-4 rounded-full animate-pulse delay-75" />
          </div>

          {/* Glowing Radial Push-To-Talk Button */}
          <button
            onClick={() => setActiveTab('voice')}
            className="w-10 h-10 rounded-full bg-gradient-to-tr from-cyan-600 to-cyan-400 p-[1px] shadow-[0_0_15px_rgba(0,200,255,0.4)] hover:shadow-[0_0_25px_rgba(0,200,255,0.8)] transition-all flex items-center justify-center group"
          >
            <div className="w-full h-full rounded-full bg-[#030c18] flex items-center justify-center group-hover:bg-cyan-950 transition-colors">
              <Mic size={16} className="text-cyan-300" />
            </div>
          </button>
          <span className="text-[9px] font-mono tracking-widest text-slate-400 uppercase">
            Tap to Speak
          </span>

          <button
            onClick={() => useJarvisStore.getState().setTheme(useJarvisStore.getState().theme === 'focus' ? 'work' : 'focus')}
            className="w-full py-1 text-[9px] font-mono text-slate-400 hover:text-amber-300 border border-slate-800 rounded bg-[#030912] flex items-center justify-center gap-1 transition-colors"
          >
            <Flame size={10} className="text-amber-400" /> Focus Mode
          </button>
        </div>
      )}

      {/* Collapse / Expand Toggle Button */}
      <button 
        onClick={toggleSidebar}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-10 rounded-full flex items-center justify-center z-20 bg-[#07172b] border border-cyan-500/30 text-cyan-400 hover:text-cyan-200 transition-colors shadow-lg"
      >
        {sidebarCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
      </button>
    </aside>
  )
}
