/**
 * VoiceView.jsx — Dedicated Voice Chat Interface
 * ================================================
 * A full-screen voice conversation mode with the JARVIS orb,
 * push-to-talk, live waveform, and transcript display.
 */

import React, { useState, useEffect, useRef } from 'react'
import { Mic, Square, Volume2, VolumeX } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import axios from 'axios'

import useJarvisStore from '../store/useJarvisStore'
import useVoice from '../hooks/useVoice'
import JarvisOrb from './JarvisOrb'

export default function VoiceView() {
  const [transcript, setTranscript] = useState([])
  const [isMuted, setIsMuted] = useState(false)
  const transcriptEndRef = useRef(null)

  const {
    activeSessionId,
    jarvisState,
    setJarvisState,
    createSession,
  } = useJarvisStore()

  const { isRecording, startRecording, stopRecording, audioData } = useVoice()

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  // Ensure we have an active session
  useEffect(() => {
    if (!activeSessionId) {
      createSession()
    }
  }, [activeSessionId, createSession])

  const handleVoiceToggle = async () => {
    if (isRecording) {
      stopRecording()
    } else {
      try {
        const transcribedText = await startRecording()
        if (transcribedText && transcribedText.trim()) {
          // Add user transcript
          setTranscript(prev => [...prev, { role: 'user', content: transcribedText.trim() }])

          // Send to backend with voice enabled
          setJarvisState('thinking')
          try {
            const res = await axios.post('http://localhost:8080/api/message', {
              session_id: activeSessionId,
              content: transcribedText.trim(),
              use_voice: !isMuted,
            })
            if (res.data.response) {
              setTranscript(prev => [...prev, { role: 'jarvis', content: res.data.response }])
            }
          } catch (err) {
            setTranscript(prev => [...prev, {
              role: 'jarvis',
              content: 'Voice link to my reasoning core was interrupted, sir.'
            }])
          }
          setJarvisState('idle')
        }
      } catch (err) {
        console.error('Voice recording error:', err)
      }
    }
  }

  const stateLabel = {
    idle: 'Awaiting Command',
    listening: 'Listening...',
    thinking: 'Processing...',
    speaking: 'Speaking...',
  }

  return (
    <div className="flex flex-col h-full w-full items-center" style={{ background: 'var(--bg-primary)' }}>

      {/* Top Section: Orb + State */}
      <div className="flex flex-col items-center justify-center flex-1 w-full max-w-2xl px-6">

        {/* JARVIS Orb — Large */}
        <div className="relative mb-8">
          <JarvisOrb size="lg" state={jarvisState} audioData={audioData} />
          
          {/* Pulsing ring when listening */}
          {isRecording && (
            <div className="absolute inset-0 rounded-full animate-ping opacity-20"
                 style={{ border: '2px solid var(--accent)' }} />
          )}
        </div>

        {/* State Label */}
        <p className="text-sm uppercase tracking-[0.3em] mb-6"
           style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
          {stateLabel[jarvisState] || 'Standby'}
        </p>

        {/* Push-to-Talk Button */}
        <button
          onClick={handleVoiceToggle}
          className="relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 group"
          style={isRecording ? {
            background: 'var(--red)',
            boxShadow: '0 0 40px rgba(255,23,68,0.5), 0 0 80px rgba(255,23,68,0.2)',
          } : {
            background: 'var(--bg-tertiary)',
            border: '2px solid var(--border-bright)',
            boxShadow: '0 0 20px var(--accent-glow)',
          }}
        >
          {isRecording ? (
            <Square size={28} className="fill-white text-white" />
          ) : (
            <Mic size={28} style={{ color: 'var(--accent)' }} />
          )}
        </button>

        <p className="mt-4 text-xs uppercase tracking-widest"
           style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
          {isRecording ? 'Tap to stop' : 'Tap to speak'}
        </p>

        {/* Mute TTS toggle */}
        <button
          onClick={() => setIsMuted(!isMuted)}
          className="mt-4 flex items-center gap-2 px-3 py-1.5 rounded-full text-xs transition-all"
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            color: isMuted ? 'var(--red)' : 'var(--text-secondary)',
          }}
        >
          {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
          {isMuted ? 'Voice Response Off' : 'Voice Response On'}
        </button>
      </div>

      {/* Bottom Section: Conversation Transcript */}
      {transcript.length > 0 && (
        <div className="w-full max-w-2xl flex-shrink-0 overflow-y-auto px-6 pb-6"
             style={{ maxHeight: '40%', borderTop: '1px solid var(--border)' }}>
          <p className="text-xs uppercase tracking-widest py-3 sticky top-0"
             style={{
               fontFamily: 'var(--font-mono)',
               color: 'var(--text-tertiary)',
               background: 'var(--bg-primary)',
             }}>
            Conversation Transcript
          </p>
          <div className="space-y-3">
            {transcript.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className="max-w-lg rounded-xl px-4 py-3 text-sm"
                     style={msg.role === 'user' ? {
                       background: 'var(--bg-hover)',
                       border: '1px solid var(--border)',
                       color: 'var(--text-primary)',
                     } : {
                       background: 'transparent',
                       color: 'var(--text-primary)',
                     }}>
                  {msg.role === 'jarvis' ? (
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </div>
      )}
    </div>
  )
}
