import React, { useState, useEffect, useRef } from 'react'
import { Send, Mic, Square, CornerDownLeft } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-dark.css'
import axios from 'axios'

import useJarvisStore from '../store/useJarvisStore'
import useVoice from '../hooks/useVoice'
import JarvisOrb from './JarvisOrb'

export default function ChatView() {
  const [inputText, setInputText] = useState('')
  const messagesEndRef = useRef(null)
  
  const { 
    messages, 
    activeSessionId, 
    isStreaming, 
    streamingContent, 
    jarvisState, 
    addMessage,
    setJarvisState
  } = useJarvisStore()

  const { isRecording, startRecording, stopRecording, audioData } = useVoice()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent])

  const handleSend = async () => {
    if (!inputText.trim() || !activeSessionId) return
    if (isRecording) stopRecording()

    const content = inputText.trim()
    setInputText('')

    addMessage({
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    })

    setJarvisState('thinking')
    
    try {
      const res = await axios.post('http://localhost:8080/api/message', {
        session_id: activeSessionId,
        content: content,
        use_voice: false 
      })
      // If WS didn't handle it, use REST response
      if (res.data.response) {
        addMessage({
          role: 'jarvis',
          content: res.data.response,
          timestamp: new Date().toISOString()
        })
      }
      setJarvisState('idle')
    } catch (e) {
      console.error(e)
      addMessage({
        role: 'jarvis',
        content: 'Connection to my reasoning core failed, sir. Please check that the backend server is running.',
        timestamp: new Date().toISOString()
      })
      setJarvisState('idle')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleVoice = () => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording().then((transcribedText) => {
        if (transcribedText && transcribedText.trim()) {
          addMessage({ role: 'user', content: transcribedText, timestamp: new Date().toISOString() })
          axios.post('http://localhost:8080/api/message', {
            session_id: activeSessionId,
            content: transcribedText,
            use_voice: true 
          })
        }
      }).catch(console.error)
    }
  }

  return (
    <div className="flex flex-col h-full w-full relative" style={{ background: 'var(--bg-primary)' }}>
      
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && !isStreaming && (
          <div className="h-full flex flex-col items-center justify-center" style={{ color: 'var(--text-tertiary)', opacity: 0.6 }}>
            <JarvisOrb size="lg" state="idle" />
            <p className="mt-8 text-sm uppercase tracking-widest" style={{ fontFamily: 'var(--font-mono)' }}>
              System Ready
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
            <div className="max-w-3xl rounded-2xl px-5 py-4"
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
                  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {/* Streaming Message */}
        {isStreaming && streamingContent && (
          <div className="flex justify-start animate-fade-in">
            <div className="max-w-3xl rounded-2xl px-5 py-4 markdown-content" style={{ color: 'var(--text-primary)' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {streamingContent}
              </ReactMarkdown>
              <span className="streaming-cursor"></span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="px-4 pb-4 pt-2" style={{ background: 'var(--bg-primary)', borderTop: '1px solid var(--border)' }}>
        <div className="max-w-4xl mx-auto relative flex items-end gap-2 rounded-2xl p-2"
             style={{
               background: 'var(--bg-secondary)',
               border: '1px solid var(--border)',
               boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
             }}>
          
          {/* Mic Button */}
          <button 
            onClick={toggleVoice}
            className="p-3 rounded-full flex-shrink-0 transition-all"
            style={isRecording ? {
              background: 'var(--red)',
              color: 'white',
              boxShadow: '0 0 15px rgba(255,23,68,0.5)',
            } : {
              background: 'var(--bg-tertiary)',
              color: 'var(--text-secondary)',
            }}
          >
            {isRecording ? <Square size={20} className="fill-current" /> : <Mic size={20} />}
          </button>

          {/* Input or Waveform */}
          <div className="flex-1 relative pb-1">
            {isRecording ? (
              <div className="h-10 flex items-center px-4">
                <JarvisOrb size="sm" state="listening" audioData={audioData} />
                <span className="ml-4 text-sm uppercase tracking-widest animate-pulse"
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                  Listening...
                </span>
              </div>
            ) : (
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message JARVIS..."
                className="w-full bg-transparent px-4 py-2 max-h-48 overflow-y-auto focus:outline-none focus:ring-0 leading-relaxed border-none resize-none"
                style={{
                  color: 'var(--text-primary)',
                  minHeight: '44px',
                  fontFamily: 'var(--font-sans)',
                }}
                rows={1}
                autoFocus
              />
            )}
          </div>

          {/* Send Button */}
          {!isRecording && (
            <button 
              onClick={handleSend}
              disabled={!inputText.trim()}
              className="p-3 rounded-xl flex-shrink-0 transition-all mb-1 disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: inputText.trim() ? 'var(--accent)' : 'var(--bg-tertiary)',
                color: inputText.trim() ? 'var(--bg-primary)' : 'var(--text-tertiary)',
                boxShadow: inputText.trim() ? '0 0 12px var(--accent-glow)' : 'none',
              }}
            >
              <CornerDownLeft size={18} strokeWidth={3} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
