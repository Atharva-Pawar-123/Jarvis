import React from 'react'
import { Settings as SettingsIcon, Palette } from 'lucide-react'
import useJarvisStore from '../store/useJarvisStore'

export default function SettingsView() {
  const { theme, setTheme } = useJarvisStore()

  const themes = [
    { id: 'work', name: 'Work Mode', desc: 'Iron Man Cyan', color: '#00C8FF' },
    { id: 'focus', name: 'Focus Mode', desc: 'Amber / Gold', color: '#FFB300' },
    { id: 'casual', name: 'Casual Mode', desc: 'Violet / Purple', color: '#9B3FFF' },
  ]

  return (
    <div className="flex-1 flex flex-col p-8 h-full overflow-y-auto" style={{ background: 'var(--bg-primary)' }}>
      <div className="flex items-center gap-3 mb-8">
        <SettingsIcon style={{ color: 'var(--accent)' }} size={28} />
        <h2 className="text-2xl font-bold uppercase tracking-wider"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
          System Preferences
        </h2>
      </div>

      <div className="max-w-3xl space-y-8">
        <div className="p-6 rounded-xl"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2 mb-6">
            <Palette style={{ color: 'var(--text-secondary)' }} size={20} />
            <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>Interface Theme</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {themes.map(t => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className="p-5 rounded-xl text-left transition-all"
                style={{
                  border: theme === t.id ? '2px solid var(--accent)' : '2px solid var(--border)',
                  background: theme === t.id ? 'var(--accent-glow)' : 'var(--bg-tertiary)',
                }}
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-5 h-5 rounded-full shadow-lg" style={{ backgroundColor: t.color }} />
                  <span className="font-semibold"
                        style={{ color: theme === t.id ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {t.name}
                  </span>
                </div>
                <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>{t.desc}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
