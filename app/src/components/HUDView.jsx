import React from 'react'
import { Cpu, Activity, HardDrive, Zap } from 'lucide-react'

export default function HUDView() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 h-full overflow-y-auto"
         style={{ background: 'var(--bg-primary)' }}>
      <div className="max-w-lg text-center space-y-6">
        {/* Animated Arc Reactor */}
        <div className="relative w-32 h-32 mx-auto">
          <div className="absolute inset-0 rounded-full"
               style={{
                 border: '3px solid var(--accent)',
                 borderTopColor: 'transparent',
                 animation: 'orb-rotate-amber 2s linear infinite',
               }} />
          <div className="absolute inset-3 rounded-full"
               style={{
                 border: '2px solid var(--violet)',
                 borderBottomColor: 'transparent',
                 animation: 'orb-rotate-amber 3s linear infinite reverse',
               }} />
          <div className="absolute inset-6 rounded-full flex items-center justify-center"
               style={{ background: 'var(--accent-glow)' }}>
            <Zap size={36} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        
        <h2 className="text-3xl font-bold uppercase tracking-widest"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
          HUD Module
        </h2>
        <p className="leading-relaxed"
           style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
          Tactical HUD Dashboard is currently in standby mode.
          Power routing is diverted to core reasoning systems.
          Stand by for Mark IV module upgrades.
        </p>
        
        {/* Status Indicators */}
        <div className="grid grid-cols-3 gap-4 mt-8">
          {[
            { icon: Cpu, label: 'CPU Core', status: 'Online' },
            { icon: Activity, label: 'Neural Net', status: 'Active' },
            { icon: HardDrive, label: 'Memory', status: 'Synced' },
          ].map((item, i) => (
            <div key={i} className="p-3 rounded-lg text-center"
                 style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
              <item.icon size={20} className="mx-auto mb-2" style={{ color: 'var(--accent)' }} />
              <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
                {item.label}
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                {item.status}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
