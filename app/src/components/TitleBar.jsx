import React from 'react'
import { Minus, Square, X, Shield, Activity } from 'lucide-react'
import useJarvisStore from '../store/useJarvisStore'
import JarvisOrb from './JarvisOrb'

export default function TitleBar() {
  const { isConnected, jarvisState } = useJarvisStore()

  const handleMinimize = () => window.jarvisAPI?.minimize()
  const handleMaximize = () => window.jarvisAPI?.maximize()
  const handleClose = () => window.jarvisAPI?.close()

  return (
    <div className="title-bar h-12 w-full flex items-center justify-between select-none z-50"
         style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
      
      {/* Left: Branding & Orb */}
      <div className="flex items-center h-full px-4 gap-3">
        <JarvisOrb size="sm" state={jarvisState} />
        <div className="flex flex-col">
          <span className="font-bold text-sm tracking-widest uppercase leading-none"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)', letterSpacing: '0.2em' }}>
            J.A.R.V.I.S.
          </span>
          <span className="text-xs uppercase mt-0.5"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', letterSpacing: '0.12em', fontSize: '9px' }}>
            Mark III • Local System
          </span>
        </div>
      </div>

      {/* Middle: Connection Status */}
      <div className="flex items-center justify-center flex-1">
        <div className="flex items-center gap-2 px-3 py-1 rounded-full text-xs tracking-wider"
             style={{
               fontFamily: 'var(--font-mono)',
               border: `1px solid ${isConnected ? 'var(--accent-glow)' : 'var(--red)'}`,
               color: isConnected ? 'var(--accent)' : 'var(--red)',
               background: isConnected ? 'var(--accent-glow)' : 'rgba(255,23,68,0.15)',
             }}>
          {isConnected ? <Shield size={12} /> : <Activity size={12} />}
          {isConnected ? 'SECURE LINK' : 'OFFLINE'}
        </div>
      </div>

      {/* Right: Window Controls */}
      <div className="flex items-center h-full">
        <button onClick={handleMinimize}
                className="h-full px-4 hover:opacity-80 transition-opacity"
                style={{ color: 'var(--text-secondary)' }}>
          <Minus size={16} />
        </button>
        <button onClick={handleMaximize}
                className="h-full px-4 hover:opacity-80 transition-opacity"
                style={{ color: 'var(--text-secondary)' }}>
          <Square size={14} />
        </button>
        <button onClick={handleClose}
                className="h-full px-4 transition-colors hover:text-white"
                style={{ color: 'var(--text-secondary)' }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--red)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
          <X size={16} />
        </button>
      </div>
    </div>
  )
}
