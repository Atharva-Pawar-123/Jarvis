import React from 'react'

export default function JarvisOrb({ size = 'md', state = 'idle', audioData }) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-16 h-16',
    lg: 'w-32 h-32'
  }

  const containerClass = sizeClasses[size] || sizeClasses.md

  // Dynamic visual state class mapping
  const stateClass = `orb-${state}` // Matches globals.css animations

  // If in listening mode and we have audioData, draw the waveform
  if (state === 'listening' && audioData && audioData.length > 0) {
    // Only use a slice of the frequency data for visualization
    const bars = Array.from(audioData).slice(0, 32)
    return (
      <div className={`flex items-center justify-center gap-[2px] ${containerClass}`}>
        {bars.map((val, i) => {
          const height = Math.max(10, (val / 255) * 100)
          return (
            <div 
              key={i} 
              className="waveform-bar"
              style={{ height: `${height}%` }}
            />
          )
        })}
      </div>
    )
  }

  return (
    <div className={`relative rounded-full flex items-center justify-center ${containerClass}`}>
      {/* Outer ring */}
      <div className={`absolute inset-0 rounded-full border border-[var(--accent)] opacity-20 ${stateClass}`} />
      
      {/* Inner solid orb */}
      <div className={`absolute inset-[10%] rounded-full bg-gradient-to-br from-[var(--accent)] to-[var(--violet)] ${stateClass}`} style={{ filter: 'blur(2px)' }} />
      
      {/* Center core highlight */}
      <div className="absolute inset-[30%] rounded-full bg-white opacity-40 blur-[1px]" />
    </div>
  )
}
