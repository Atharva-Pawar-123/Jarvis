import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Cpu, HardDrive, Activity, Thermometer, Zap, Layers, RefreshCw, Radio, ShieldCheck } from 'lucide-react'
import ArcReactorCanvas from './ArcReactorCanvas'

export default function HUDView() {
  const [telemetry, setTelemetry] = useState({
    cpu_percent: 0,
    ram_percent: 0,
    gpu_vram_percent: 0,
    vram_used_mb: 0,
    vram_total_mb: 6144,
    gpu_temp_c: 0,
    disk_percent: 0,
    active_consumer: 'llm',
    uptime: '0s',
    session_count: 0,
    total_messages: 0,
  })
  const [loading, setLoading] = useState(true)

  const fetchTelemetry = async () => {
    try {
      const [sysRes, gpuRes] = await Promise.all([
        axios.get('http://localhost:8080/api/system/status').catch(() => ({ data: {} })),
        axios.get('http://localhost:8080/api/gpu/telemetry').catch(() => ({ data: {} }))
      ])

      setTelemetry({
        cpu_percent: sysRes.data.cpu_percent || 0,
        ram_percent: sysRes.data.ram_percent || 0,
        disk_percent: sysRes.data.disk_percent || 0,
        uptime: sysRes.data.uptime || '0s',
        session_count: sysRes.data.session_count || 0,
        total_messages: sysRes.data.total_messages || 0,
        gpu_vram_percent: gpuRes.data.vram_percent || 0,
        vram_used_mb: gpuRes.data.vram_used_mb || 0,
        vram_total_mb: gpuRes.data.vram_total_mb || 6144,
        gpu_temp_c: gpuRes.data.gpu_temp_c || 0,
        active_consumer: gpuRes.data.active_consumer || 'llm'
      })
    } catch (e) {
      console.error('HUD telemetry poll failed', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTelemetry()
    const timer = setInterval(fetchTelemetry, 3000)
    return () => clearInterval(timer)
  }, [])

  const CircularMeter = ({ percent, label, valueText, icon: Icon, color = 'var(--accent)' }) => {
    const strokeWidth = 8
    const radius = 38
    const circumference = 2 * Math.PI * radius
    const strokeDashoffset = circumference - (percent / 100) * circumference

    return (
      <div className="flex flex-col items-center p-4 rounded-xl relative"
           style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
        <div className="relative w-28 h-28 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 96 96">
            <circle
              cx="48" cy="48" r={radius}
              stroke="var(--bg-tertiary)"
              strokeWidth={strokeWidth}
              fill="transparent"
            />
            <circle
              cx="48" cy="48" r={radius}
              stroke={color}
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              fill="transparent"
              style={{ transition: 'stroke-dashoffset 0.5s ease-in-out' }}
            />
          </svg>
          <div className="absolute flex flex-col items-center justify-center text-center">
            <Icon size={16} style={{ color }} className="mb-0.5" />
            <span className="font-mono text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
              {percent}%
            </span>
          </div>
        </div>
        <div className="mt-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
          {label}
        </div>
        <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
          {valueText}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col p-6 h-full overflow-y-auto relative z-10" style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ background: 'var(--accent-glow)' }}>
            <Activity style={{ color: 'var(--accent)' }} size={24} />
          </div>
          <div>
            <h2 className="text-xl font-bold uppercase tracking-wider"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
              Tactical HUD Telemetry
            </h2>
            <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              Live hardware metrics & VRAM allocation across NVIDIA RTX 3050 & Host
            </p>
          </div>
        </div>
        <button
          onClick={fetchTelemetry}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors"
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--accent)' }}
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Central Arc Reactor Core + Telemetry Visualizer */}
      <div className="mb-6 p-6 rounded-2xl border border-cyan-500/25 bg-[#030d1a]/70 backdrop-blur-md shadow-[0_0_30px_rgba(0,200,255,0.08)] flex flex-col lg:flex-row items-center justify-between gap-6">
        <div className="flex-1 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/30 text-cyan-300 font-mono text-[11px] mb-3">
            <Radio size={12} className="animate-pulse text-cyan-400" />
            <span>PRIMARY CORE ACTIVE · MARK VII SYNCHRONIZED</span>
          </div>
          <h3 className="text-2xl font-black text-slate-100 tracking-wider font-mono mb-2">
            ARC REACTOR ENGINE
          </h3>
          <p className="text-xs text-slate-400 max-w-md font-sans leading-relaxed mb-4">
            Dynamic tactical radar and core frequency monitoring. Spin velocity and reactor thermal glow modulate proportionally with live GPU & neural processing loads.
          </p>
          <div className="flex flex-wrap gap-4 text-xs font-mono">
            <div className="px-3 py-2 rounded-xl bg-slate-900/80 border border-cyan-500/20">
              <span className="text-slate-500 block text-[10px]">CORE THERMAL</span>
              <span className="text-cyan-300 font-bold text-sm">{telemetry.gpu_temp_c}°C</span>
            </div>
            <div className="px-3 py-2 rounded-xl bg-slate-900/80 border border-cyan-500/20">
              <span className="text-slate-500 block text-[10px]">VRAM BUDGET</span>
              <span className="text-cyan-300 font-bold text-sm">{telemetry.vram_used_mb} MB</span>
            </div>
            <div className="px-3 py-2 rounded-xl bg-slate-900/80 border border-cyan-500/20">
              <span className="text-slate-500 block text-[10px]">ACTIVE SUBSYSTEM</span>
              <span className="text-amber-300 font-bold text-sm uppercase">{telemetry.active_consumer}</span>
            </div>
          </div>
        </div>

        {/* Live Rotating Arc Reactor */}
        <div className="relative flex items-center justify-center p-2">
          <ArcReactorCanvas
            activeLoad={Math.max(telemetry.cpu_percent, telemetry.gpu_vram_percent)}
            size={340}
          />
        </div>
      </div>

      {/* Main Gauges Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <CircularMeter
          percent={Math.round(telemetry.cpu_percent)}
          label="CPU Core Usage"
          valueText={`${Math.round(telemetry.cpu_percent)}% Active`}
          icon={Cpu}
          color="var(--accent)"
        />
        <CircularMeter
          percent={Math.round(telemetry.ram_percent)}
          label="System RAM"
          valueText={`${Math.round(telemetry.ram_percent)}% Allocated`}
          icon={HardDrive}
          color="var(--cyan)"
        />
        <CircularMeter
          percent={Math.round(telemetry.gpu_vram_percent)}
          label="GPU VRAM"
          valueText={`${telemetry.vram_used_mb} / ${telemetry.vram_total_mb} MB`}
          icon={Zap}
          color="var(--amber)"
        />
        <CircularMeter
          percent={Math.min(100, Math.round((telemetry.gpu_temp_c / 90) * 100))}
          label="GPU Thermal"
          valueText={`${telemetry.gpu_temp_c}°C`}
          icon={Thermometer}
          color={telemetry.gpu_temp_c > 75 ? 'var(--red)' : 'var(--accent)'}
        />
      </div>

      {/* System Status Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="p-4 rounded-xl flex items-center justify-between"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div>
            <div className="text-xs font-mono uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Active VRAM Consumer
            </div>
            <div className="text-base font-bold font-mono mt-1" style={{ color: 'var(--accent)' }}>
              {telemetry.active_consumer.toUpperCase()}
            </div>
          </div>
          <Layers size={24} style={{ color: 'var(--accent)', opacity: 0.8 }} />
        </div>

        <div className="p-4 rounded-xl flex items-center justify-between"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div>
            <div className="text-xs font-mono uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Core Engine Uptime
            </div>
            <div className="text-base font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {telemetry.uptime}
            </div>
          </div>
          <Activity size={24} style={{ color: 'var(--text-secondary)', opacity: 0.8 }} />
        </div>

        <div className="p-4 rounded-xl flex items-center justify-between"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div>
            <div className="text-xs font-mono uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Database Dialogues
            </div>
            <div className="text-base font-bold font-mono mt-1" style={{ color: 'var(--text-primary)' }}>
              {telemetry.session_count} Sessions ({telemetry.total_messages} msgs)
            </div>
          </div>
          <HardDrive size={24} style={{ color: 'var(--text-secondary)', opacity: 0.8 }} />
        </div>
      </div>
    </div>
  )
}
