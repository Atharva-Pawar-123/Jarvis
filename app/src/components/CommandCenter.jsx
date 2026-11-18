import React, { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Shield,
  Activity,
  Cpu,
  HardDrive,
  Zap,
  Radio,
  Clock,
  Compass,
  CheckCircle2,
  AlertTriangle,
  Info,
  Sparkles,
  Calendar,
  MessageSquare,
  Bot,
  Terminal,
  Search,
  ExternalLink,
  ChevronRight,
  Play,
  RotateCcw,
  Sliders,
  Flame,
  Volume2,
  Mic,
  Maximize2
} from 'lucide-react'
import useJarvisStore from '../store/useJarvisStore'

export default function CommandCenter() {
  const { setActiveTab, setJarvisState, activeSessionId, jarvisState } = useJarvisStore()

  // Hardware telemetry state
  const [telemetry, setTelemetry] = useState({
    cpu_percent: 15,
    ram_percent: 54,
    disk_percent: 40,
    gpu_vram_percent: 32,
    vram_used_mb: 1966,
    vram_total_mb: 6144,
    gpu_temp_c: 48,
    active_consumer: 'llm'
  })

  // Live time ticker
  const [currentTime, setCurrentTime] = useState(new Date())
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Telemetry fetcher
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const [sysRes, gpuRes] = await Promise.all([
          axios.get('http://localhost:8080/api/system/status').catch(() => ({ data: {} })),
          axios.get('http://localhost:8080/api/gpu/telemetry').catch(() => ({ data: {} }))
        ])
        if (sysRes.data.cpu_percent !== undefined) {
          setTelemetry(prev => ({
            ...prev,
            cpu_percent: sysRes.data.cpu_percent || 15,
            ram_percent: sysRes.data.ram_percent || 54,
            disk_percent: sysRes.data.disk_percent || 40,
            gpu_vram_percent: gpuRes.data.vram_percent || 32,
            vram_used_mb: gpuRes.data.vram_used_mb || 1966,
            vram_total_mb: gpuRes.data.vram_total_mb || 6144,
            gpu_temp_c: gpuRes.data.gpu_temp_c || 48,
            active_consumer: gpuRes.data.active_consumer || 'llm'
          }))
        }
      } catch (e) {
        // Fallback default telemetry
      }
    }
    fetchTelemetry()
    const interval = setInterval(fetchTelemetry, 3000)
    return () => clearInterval(interval)
  }, [])

  // Format date and time
  const formattedDate = currentTime.toLocaleDateString('en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  })

  const formattedTime = currentTime.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  }).toLowerCase()

  // Circular gauge component
  const CircularDial = ({ percent, label, valueText, color = '#00C8FF' }) => {
    const radius = 34
    const circumference = 2 * Math.PI * radius
    const offset = circumference - (percent / 100) * circumference

    return (
      <div className="flex flex-col items-center justify-center p-2">
        <div className="relative w-20 h-20 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 80 80">
            <circle
              cx="40"
              cy="40"
              r={radius}
              stroke="rgba(0, 200, 255, 0.08)"
              strokeWidth="6"
              fill="transparent"
            />
            <circle
              cx="40"
              cy="40"
              r={radius}
              stroke={color}
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              fill="transparent"
              style={{ transition: 'stroke-dashoffset 0.6s ease' }}
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="font-mono text-xs font-bold text-cyan-300">
              {percent}%
            </span>
          </div>
        </div>
        <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400 mt-1">
          {label}
        </span>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto select-none bg-[#02060D] text-slate-200">
      
      {/* ── Top HUD Header ────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-2 border-b border-cyan-500/20 bg-[#040C18]/80 backdrop-blur-md sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-400 font-mono text-xs font-semibold tracking-wider">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#00c8ff]" />
            SYSTEM STATUS <span className="text-emerald-400 font-bold ml-1">OPTIMAL</span>
          </div>
        </div>

        {/* Center Clock */}
        <div className="flex flex-col items-center justify-center">
          <span className="text-[11px] font-mono tracking-widest text-slate-400 uppercase">
            {formattedDate}
          </span>
          <span className="text-xl font-mono font-bold tracking-widest text-cyan-300 drop-shadow-[0_0_12px_rgba(0,200,255,0.6)]">
            {formattedTime}
          </span>
        </div>

        {/* Right Tools / Operator */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search..."
              className="w-48 pl-8 pr-3 py-1 rounded bg-[#071324] border border-cyan-900/50 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 font-mono"
            />
          </div>
          <div className="flex items-center gap-2 px-3 py-1 rounded bg-[#071324] border border-cyan-900/40 text-xs">
            <div className="w-5 h-5 rounded-full bg-cyan-500/20 flex items-center justify-center border border-cyan-400/40">
              <Shield size={11} className="text-cyan-400" />
            </div>
            <div className="flex flex-col text-left">
              <span className="text-[10px] font-bold text-slate-300 leading-tight">Operator</span>
              <span className="text-[8px] font-mono text-cyan-400 leading-none">Commander</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main Command Center Matrix ────────────────────────────────── */}
      <div className="p-4 grid grid-cols-12 gap-4 flex-1">
        
        {/* ROW 1: AI Core Overview + Holographic Central Orb + Live Intelligence Feed */}
        
        {/* Left Column: AI Core Overview */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-2 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md relative overflow-hidden">
          <div className="absolute top-0 left-0 w-16 h-1 bg-cyan-400/80 shadow-[0_0_8px_#00c8ff]" />
          <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400 mb-2 flex items-center justify-between">
            <span>AI Core Overview</span>
            <Activity size={13} className="text-cyan-400" />
          </h3>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
              <div>
                <div className="text-[10px] text-slate-400">AI Core</div>
                <div className="font-bold text-cyan-200">Active</div>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#00c8ff]" />
              <div>
                <div className="text-[10px] text-slate-400">Memory</div>
                <div className="font-bold text-cyan-200">3,380 Stored</div>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
              <div>
                <div className="text-[10px] text-slate-400">Voice</div>
                <div className="font-bold text-cyan-200">Online</div>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#00c8ff]" />
              <div>
                <div className="text-[10px] text-slate-400">Agents</div>
                <div className="font-bold text-cyan-200">2 Running</div>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-400 shadow-[0_0_6px_#f59e0b]" />
              <div>
                <div className="text-[10px] text-slate-400">LLMs</div>
                <div className="font-bold text-cyan-200">4 Connected</div>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
              <div>
                <div className="text-[10px] text-slate-400">System</div>
                <div className="font-bold text-emerald-400">Optimal</div>
              </div>
            </div>
          </div>
        </div>

        {/* Center Holographic AI Sphere */}
        <div className="col-span-12 lg:col-span-6 flex flex-col items-center justify-center p-6 rounded-xl border border-cyan-500/20 bg-gradient-to-b from-[#051124]/90 to-[#020712] relative overflow-hidden group">
          {/* Subtle grid pattern background */}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,200,255,0.08)_0%,transparent_70%)]" />

          {/* 3D Holographic Arc Reactor Globe */}
          <div className="relative w-48 h-48 flex items-center justify-center mb-4">
            {/* Outer spinning dashed ring */}
            <div className="absolute inset-0 rounded-full border border-dashed border-cyan-400/40 animate-[spin_24s_linear_infinite]" />
            {/* Counter-spinning second ring */}
            <div className="absolute inset-3 rounded-full border border-dotted border-cyan-300/30 animate-[spin_16s_linear_infinite_reverse]" />
            {/* Elliptical orbital rings */}
            <div className="absolute inset-[-10px] rounded-[50%] border border-cyan-400/25 rotate-45 animate-pulse" />
            <div className="absolute inset-[-10px] rounded-[50%] border border-cyan-400/25 -rotate-45 animate-pulse" />

            {/* Glowing Particle Sphere Core */}
            <div className="w-32 h-32 rounded-full bg-gradient-to-tr from-cyan-600/30 via-cyan-400/10 to-blue-500/30 border border-cyan-400/60 flex flex-col items-center justify-center shadow-[0_0_35px_rgba(0,200,255,0.35)] backdrop-blur-sm relative">
              <span className="font-mono text-xs font-black tracking-[0.3em] text-cyan-200 uppercase drop-shadow-[0_0_8px_#00c8ff]">
                JARVIS
              </span>
              <span className="text-[9px] font-mono tracking-widest text-cyan-400/80 mt-1 uppercase">
                AI CORE
              </span>
              <span className="text-[8px] font-mono text-slate-500 mt-0.5">
                v3.0.0
              </span>
            </div>
          </div>

          <div className="text-center font-mono z-10">
            <span className="text-xs uppercase tracking-[0.25em] text-cyan-400 font-bold">
              Autonomous Intelligence Array Active
            </span>
            <p className="text-[10px] text-slate-400 mt-1">
              Neural reasoning engine synchronized with local hardware
            </p>
          </div>
        </div>

        {/* Right Column: Live Intelligence Feed */}
        <div className="col-span-12 lg:col-span-3 flex flex-col p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400 flex items-center gap-1.5">
              <span>Live Intelligence Feed</span>
            </h3>
            <span className="px-1.5 py-0.5 text-[9px] font-mono bg-emerald-950/80 border border-emerald-500/40 text-emerald-400 rounded">
              ● LIVE
            </span>
          </div>

          <div className="flex-1 flex flex-col gap-2 overflow-y-auto max-h-56 pr-1 text-xs">
            <div className="p-2.5 rounded-lg bg-[#08172c]/90 border-l-2 border-cyan-400 border-t border-r border-b border-cyan-900/30">
              <div className="flex items-center justify-between text-[10px] text-cyan-400 font-mono">
                <span className="font-bold">Design review with the team</span>
                <span className="text-slate-500">INFO</span>
              </div>
              <p className="text-[11px] text-slate-300 mt-1 leading-tight">Meeting scheduled for HUD deployment discussion.</p>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/90 border-l-2 border-amber-400 border-t border-r border-b border-cyan-900/30">
              <div className="flex items-center justify-between text-[10px] text-amber-400 font-mono">
                <span className="font-bold">2 tasks are overdue</span>
                <span className="text-amber-500">WARN</span>
              </div>
              <p className="text-[11px] text-slate-300 mt-1 leading-tight">Review voice pipeline checkpoints & task queue.</p>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/90 border-l-2 border-cyan-400 border-t border-r border-b border-cyan-900/30">
              <div className="flex items-center justify-between text-[10px] text-cyan-400 font-mono">
                <span className="font-bold">3 pull requests awaiting review</span>
                <span className="text-slate-500">TIP</span>
              </div>
              <p className="text-[11px] text-slate-300 mt-1 leading-tight">Git worktree branches ready for verification.</p>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/90 border-l-2 border-emerald-400 border-t border-r border-b border-cyan-900/30">
              <div className="flex items-center justify-between text-[10px] text-emerald-400 font-mono">
                <span className="font-bold">CPU usage at 15%</span>
                <span className="text-emerald-500">LIVE</span>
              </div>
              <p className="text-[11px] text-slate-300 mt-1 leading-tight">System load nominal across all thread pools.</p>
            </div>
          </div>

          <button className="mt-2 text-right text-[10px] font-mono text-cyan-400 hover:underline flex items-center justify-end gap-1">
            View All Intelligence <ChevronRight size={10} />
          </button>
        </div>

        {/* ROW 2: Active Agents Grid + Mission Timeline + Quick Commands */}

        {/* Active Agents */}
        <div className="col-span-12 lg:col-span-5 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400">
              Active Agents
            </h3>
            <span className="text-[10px] font-mono text-slate-400 hover:text-cyan-300 cursor-pointer">
              View All &gt;
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal size={14} className="text-cyan-400" />
                <div>
                  <div className="text-xs font-bold text-slate-200">Coding Agent</div>
                  <div className="text-[10px] text-emerald-400 font-mono">● Active</div>
                </div>
              </div>
              <div className="flex items-end gap-0.5 h-4">
                <div className="w-1 bg-cyan-400 h-2 rounded-t animate-pulse" />
                <div className="w-1 bg-cyan-400 h-3.5 rounded-t animate-pulse delay-75" />
                <div className="w-1 bg-cyan-400 h-1.5 rounded-t animate-pulse delay-150" />
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Search size={14} className="text-cyan-400" />
                <div>
                  <div className="text-xs font-bold text-slate-200">Research Agent</div>
                  <div className="text-[10px] text-emerald-400 font-mono">● Active</div>
                </div>
              </div>
              <div className="flex items-end gap-0.5 h-4">
                <div className="w-1 bg-cyan-400 h-3 rounded-t animate-pulse" />
                <div className="w-1 bg-cyan-400 h-1.5 rounded-t animate-pulse delay-75" />
                <div className="w-1 bg-cyan-400 h-4 rounded-t animate-pulse delay-150" />
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HardDrive size={14} className="text-purple-400" />
                <div>
                  <div className="text-xs font-bold text-slate-200">Memory Agent</div>
                  <div className="text-[10px] text-slate-400 font-mono">Standby</div>
                </div>
              </div>
              <div className="w-2 h-2 rounded-full bg-slate-600" />
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Compass size={14} className="text-amber-400" />
                <div>
                  <div className="text-xs font-bold text-slate-200">Browser Agent</div>
                  <div className="text-[10px] text-slate-400 font-mono">Standby</div>
                </div>
              </div>
              <div className="w-2 h-2 rounded-full bg-slate-600" />
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity size={14} className="text-cyan-400" />
                <div>
                  <div className="text-xs font-bold text-slate-200">Task Agent</div>
                  <div className="text-[10px] text-slate-400 font-mono">Standby</div>
                </div>
              </div>
              <div className="w-2 h-2 rounded-full bg-slate-600" />
            </div>

            <div className="p-2.5 rounded-lg bg-[#08172c]/80 border border-cyan-900/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield size={14} className="text-emerald-400" />
                <div>
                  <div className="text-xs font-bold text-slate-200">System Agent</div>
                  <div className="text-[10px] text-emerald-400 font-mono">● Standby</div>
                </div>
              </div>
              <CheckCircle2 size={13} className="text-emerald-400" />
            </div>
          </div>
        </div>

        {/* Mission Timeline */}
        <div className="col-span-12 lg:col-span-4 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400">
              Mission Timeline
            </h3>
            <span className="text-[10px] font-mono text-cyan-400">Today ▼</span>
          </div>

          <div className="space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between p-2 rounded bg-[#08172c]/60 border border-cyan-950">
              <span className="text-slate-400">09:30 am</span>
              <span className="font-semibold text-slate-200">Daily Standup</span>
              <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 text-[10px]">Done</span>
            </div>

            <div className="flex items-center justify-between p-2 rounded bg-[#08172c]/60 border border-cyan-950">
              <span className="text-slate-400">12:00 pm</span>
              <span className="font-semibold text-slate-200">Finalize HUD panel spacing</span>
              <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 text-[10px]">in 42m</span>
            </div>

            <div className="flex items-center justify-between p-2 rounded bg-[#08172c]/60 border border-cyan-950">
              <span className="text-slate-400">02:00 pm</span>
              <span className="font-semibold text-cyan-300">Deep-work: Voice pipeline</span>
              <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 text-[10px]">in 2h 42m</span>
            </div>

            <div className="flex items-center justify-between p-2 rounded bg-[#08172c]/60 border border-cyan-950">
              <span className="text-slate-400">04:30 pm</span>
              <span className="font-semibold text-slate-200">Design Review Command Center V1</span>
              <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 text-[10px]">in 5h 12m</span>
            </div>
          </div>

          <button className="mt-2 text-center w-full text-[10px] font-mono text-cyan-400 hover:underline">
            View Full Schedule &gt;
          </button>
        </div>

        {/* Quick Commands */}
        <div className="col-span-12 lg:col-span-3 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md flex flex-col justify-between">
          <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400 mb-2">
            Quick Commands
          </h3>

          <div className="space-y-2">
            <button
              onClick={() => setActiveTab('tasks')}
              className="w-full flex items-center gap-2 p-2 rounded-lg bg-[#08172c] hover:bg-cyan-950/60 border border-cyan-900/50 text-xs font-mono text-cyan-300 transition-colors"
            >
              <span className="text-cyan-400 font-bold">+</span> Start New Task
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className="w-full flex items-center gap-2 p-2 rounded-lg bg-[#08172c] hover:bg-cyan-950/60 border border-cyan-900/50 text-xs font-mono text-cyan-300 transition-colors"
            >
              <Calendar size={13} className="text-cyan-400" /> Open Calendar
            </button>
            <button
              onClick={() => setActiveTab('voice')}
              className="w-full flex items-center gap-2 p-2 rounded-lg bg-[#08172c] hover:bg-cyan-950/60 border border-cyan-900/50 text-xs font-mono text-cyan-300 transition-colors"
            >
              <Mic size={13} className="text-cyan-400" /> Start Voice Chat
            </button>
            <button
              onClick={() => setActiveTab('tasks')}
              className="w-full flex items-center gap-2 p-2 rounded-lg bg-[#08172c] hover:bg-cyan-950/60 border border-cyan-900/50 text-xs font-mono text-cyan-300 transition-colors"
            >
              <Play size={13} className="text-cyan-400" /> Run Workflow
            </button>
          </div>
        </div>

        {/* ROW 3: System Monitor (Circular Gauges) + Memory Insights + LLM Status */}

        {/* System Monitor */}
        <div className="col-span-12 lg:col-span-4 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md">
          <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400 mb-2">
            System Monitor
          </h3>
          <div className="flex items-center justify-around">
            <CircularDial percent={Math.round(telemetry.cpu_percent)} label="CPU" color="#00C8FF" />
            <CircularDial percent={Math.round(telemetry.ram_percent)} label="RAM" color="#00E5FF" />
            <CircularDial percent={Math.round(telemetry.disk_percent)} label="Disk" color="#38BDF8" />
          </div>
        </div>

        {/* Memory Insights */}
        <div className="col-span-12 lg:col-span-3 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400">
              Memory Insights
            </h3>
            <span className="text-[10px] font-mono text-slate-400">3,380</span>
          </div>

          <div className="flex items-center justify-between">
            {/* Constellation SVG art */}
            <div className="w-24 h-16">
              <svg className="w-full h-full" viewBox="0 0 100 60">
                <circle cx="20" cy="30" r="2.5" fill="#00C8FF" className="animate-ping" />
                <circle cx="45" cy="15" r="2" fill="#00C8FF" />
                <circle cx="75" cy="25" r="2.5" fill="#00C8FF" />
                <circle cx="60" cy="48" r="2" fill="#00C8FF" />
                <line x1="20" y1="30" x2="45" y2="15" stroke="rgba(0,200,255,0.4)" strokeWidth="1" />
                <line x1="45" y1="15" x2="75" y2="25" stroke="rgba(0,200,255,0.4)" strokeWidth="1" />
                <line x1="75" y1="25" x2="60" y2="48" stroke="rgba(0,200,255,0.4)" strokeWidth="1" />
              </svg>
            </div>

            <div className="text-right text-xs font-mono">
              <div className="text-[10px] text-slate-400">Session Turns</div>
              <div className="text-cyan-300 font-bold">22</div>
              <div className="text-[10px] text-slate-400 mt-1">Tool Calls</div>
              <div className="text-cyan-300 font-bold">14</div>
            </div>
          </div>

          <button
            onClick={() => setActiveTab('memory')}
            className="text-[10px] font-mono text-cyan-400 hover:underline text-left mt-2"
          >
            View Memory Map &gt;
          </button>
        </div>

        {/* LLM Status Grid */}
        <div className="col-span-12 lg:col-span-5 p-4 rounded-xl border border-cyan-500/20 bg-[#061020]/70 backdrop-blur-md">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-mono font-bold tracking-widest uppercase text-cyan-400">
              LLM Status
            </h3>
            <span className="text-[10px] font-mono text-emerald-400">4 Connected</span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-slate-300 font-bold">Claude</span>
              <span className="text-[9px] text-slate-500">Not Linked</span>
            </div>
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-slate-300 font-bold">OpenAI</span>
              <span className="text-[9px] text-slate-500">Not Linked</span>
            </div>
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-slate-300 font-bold">Gemini</span>
              <span className="text-[9px] text-slate-500">Not Linked</span>
            </div>

            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-emerald-300 font-bold">Groq</span>
              <span className="text-[9px] text-emerald-400">Connected</span>
            </div>
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-slate-300 font-bold">OpenRouter</span>
              <span className="text-[9px] text-slate-500">Not Linked</span>
            </div>
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-cyan-300 font-bold">Ollama</span>
              <span className="text-[9px] text-cyan-400 font-bold">Local (qwen2.5)</span>
            </div>

            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-purple-300 font-bold">Claude Code</span>
              <span className="text-[9px] text-purple-400">Connected</span>
            </div>
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-emerald-300 font-bold">Cursor</span>
              <span className="text-[9px] text-emerald-400">Connected</span>
            </div>
            <div className="p-2 rounded bg-[#08172c]/80 border border-cyan-950 flex flex-col justify-between">
              <span className="text-emerald-300 font-bold">Copilot</span>
              <span className="text-[9px] text-emerald-400">Connected</span>
            </div>
          </div>

          <div className="text-right mt-2">
            <span className="text-[10px] font-mono text-cyan-400 hover:underline cursor-pointer">
              Manage Providers &gt;
            </span>
          </div>
        </div>

      </div>

      {/* ── Bottom Floating HUD Action Bar ────────────────────────────── */}
      <footer className="border-t border-cyan-500/20 bg-[#040C18]/90 backdrop-blur-md px-6 py-2.5 flex items-center justify-between sticky bottom-0 z-30">
        
        {/* Left: Location & Weather & Network */}
        <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-500">Location:</span>
            <span className="text-slate-300 font-semibold">Local Workstation</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-500">Weather:</span>
            <span className="text-slate-300 font-semibold">28°C Overcast</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-500">Network:</span>
            <span className="text-emerald-400 font-semibold">Excellent</span>
          </div>
        </div>

        {/* Centerpiece: Glowing TALK TO JARVIS Action Pill */}
        <button
          onClick={() => setActiveTab('voice')}
          className="group relative px-8 py-2 rounded-full bg-gradient-to-r from-cyan-950 via-cyan-900/60 to-cyan-950 border border-cyan-400/60 shadow-[0_0_20px_rgba(0,200,255,0.35)] hover:shadow-[0_0_35px_rgba(0,200,255,0.7)] transition-all flex items-center gap-3"
        >
          {/* Animated soundwave on left */}
          <div className="flex items-center gap-0.5 h-3">
            <div className="w-0.5 bg-cyan-400 h-2 rounded-full animate-pulse" />
            <div className="w-0.5 bg-cyan-400 h-3 rounded-full animate-pulse delay-75" />
            <div className="w-0.5 bg-cyan-400 h-1.5 rounded-full animate-pulse delay-150" />
          </div>

          <div className="flex flex-col items-center">
            <span className="font-mono text-xs font-black tracking-[0.25em] text-cyan-200 uppercase drop-shadow-[0_0_8px_#00c8ff]">
              TALK TO JARVIS
            </span>
            <span className="text-[9px] font-mono text-cyan-400/70 tracking-widest leading-none mt-0.5">
              I am listening...
            </span>
          </div>

          {/* Animated soundwave on right */}
          <div className="flex items-center gap-0.5 h-3">
            <div className="w-0.5 bg-cyan-400 h-1.5 rounded-full animate-pulse delay-150" />
            <div className="w-0.5 bg-cyan-400 h-3 rounded-full animate-pulse delay-75" />
            <div className="w-0.5 bg-cyan-400 h-2 rounded-full animate-pulse" />
          </div>
        </button>

        {/* Right: Executive Briefing Action */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('chat')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#071324] hover:bg-cyan-950/80 border border-cyan-500/30 text-xs font-mono text-cyan-300 transition-colors"
          >
            <Play size={12} className="text-cyan-400 fill-cyan-400" />
            <span>Executive Briefing</span>
          </button>
        </div>

      </footer>

    </div>
  )
}
