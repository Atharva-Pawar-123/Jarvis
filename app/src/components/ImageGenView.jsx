/**
 * ImageGenView.jsx — Image Generation Studio
 * ============================================
 * Dedicated image generation interface with model selection,
 * text/voice prompt input, generation history, and gallery.
 * Like Grok's image gen but for JARVIS.
 */

import React, { useState, useRef, useEffect } from 'react'
import { Image, Sparkles, Download, Trash2, Mic, Square, Loader2, ChevronDown, RefreshCw } from 'lucide-react'
import axios from 'axios'

import useJarvisStore from '../store/useJarvisStore'
import useVoice from '../hooks/useVoice'

const API_BASE = 'http://localhost:8080'

export default function ImageGenView() {
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [selectedModel, setSelectedModel] = useState('local')
  const [availableModels, setAvailableModels] = useState([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedImages, setGeneratedImages] = useState([])
  const [steps, setSteps] = useState(20)
  const [width, setWidth] = useState(512)
  const [height, setHeight] = useState(512)
  const [error, setError] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)
  const galleryEndRef = useRef(null)

  const { isRecording, startRecording, stopRecording, audioData } = useVoice()

  // Fetch available models on mount
  useEffect(() => {
    fetchModels()
  }, [])

  useEffect(() => {
    galleryEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [generatedImages])

  const fetchModels = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/image/models`)
      const models = res.data.models || []
      setAvailableModels(models)
      if (models.length > 0 && !models.some(m => m.id === selectedModel)) {
        setSelectedModel(models[0].id)
      }
    } catch {
      // Fallback explicit models list without auto
      const fallbackList = [
        { id: 'local', name: 'DreamShaper 8 (Local SD Forge)', source: 'forge', description: 'Local SD Forge — High speed on NVIDIA RTX GPU' },
        { id: 'pollinations:flux', name: 'FLUX.1 Schnell (Cloud)', source: 'pollinations', description: 'Exceptional detail, high photorealism' },
        { id: 'pollinations:flux-realism', name: 'FLUX Realism (Cloud)', source: 'pollinations', description: 'Tuned for realistic skin, portraiture & textures' },
        { id: 'pollinations:flux-anime', name: 'FLUX Anime (Cloud)', source: 'pollinations', description: 'Stylized anime, concept art, and digital illustrations' },
        { id: 'pollinations:turbo', name: 'Pollinations Turbo (Cloud)', source: 'pollinations', description: 'Fast cloud generation with clean prompt adherence' },
      ]
      setAvailableModels(fallbackList)
    }
  }

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setIsGenerating(true)
    setError('')

    try {
      const res = await axios.post(`${API_BASE}/api/image/generate`, {
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim(),
        model: selectedModel,
        steps: steps,
        width: width,
        height: height,
        enhance_prompt: true,
      }, { timeout: 120000 })

      if (res.data.image_base64) {
        const newImage = {
          id: Date.now(),
          prompt: prompt.trim(),
          image: `data:image/png;base64,${res.data.image_base64}`,
          source: res.data.source || 'Unknown',
          filepath: res.data.filepath || '',
          timestamp: new Date().toISOString(),
          enhanced_prompt: res.data.enhanced_prompt || '',
        }
        setGeneratedImages(prev => [newImage, ...prev])
        setSelectedImage(newImage)
      } else {
        setError(res.data.error || 'Image generation failed.')
      }
    } catch (err) {
      console.error('Image gen error:', err)
      setError(err.response?.data?.detail || 'Failed to connect to image generation engine.')
    }
    setIsGenerating(false)
  }

  const handleVoicePrompt = async () => {
    if (isRecording) {
      stopRecording()
    } else {
      try {
        const text = await startRecording()
        if (text && text.trim()) {
          setPrompt(text.trim())
        }
      } catch (err) {
        console.error('Voice prompt error:', err)
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleGenerate()
    }
  }

  const handleDownload = (img) => {
    const link = document.createElement('a')
    link.href = img.image
    link.download = `jarvis_gen_${img.id}.png`
    link.click()
  }

  const handleDelete = (id) => {
    setGeneratedImages(prev => prev.filter(img => img.id !== id))
    if (selectedImage?.id === id) setSelectedImage(null)
  }

  const sizePresets = [
    { label: '512×512', w: 512, h: 512 },
    { label: '512×768', w: 512, h: 768 },
    { label: '768×512', w: 768, h: 512 },
    { label: '768×768', w: 768, h: 768 },
  ]

  return (
    <div className="flex flex-col h-full w-full overflow-hidden" style={{ background: 'var(--bg-primary)' }}>

      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4"
           style={{ borderBottom: '1px solid var(--border)' }}>
        <Sparkles size={22} style={{ color: 'var(--accent)' }} />
        <h2 className="text-lg font-bold uppercase tracking-wider"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
          Image Generation
        </h2>
        <span className="text-xs px-2 py-0.5 rounded-full ml-2"
              style={{
                background: 'var(--accent-glow)',
                color: 'var(--accent)',
                fontFamily: 'var(--font-mono)',
              }}>
          STUDIO
        </span>
      </div>

      <div className="flex flex-1 overflow-hidden">

        {/* Left Panel: Controls */}
        <div className="w-[380px] flex-shrink-0 flex flex-col overflow-y-auto p-5 space-y-5"
             style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>

          {/* Model Selector */}
          <div>
            <label className="text-xs font-bold uppercase tracking-widest mb-2 block"
                   style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              Model
            </label>
            <div className="relative">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full px-4 py-3 rounded-lg appearance-none cursor-pointer text-sm"
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-sans)',
                }}
              >
                {availableModels.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                           style={{ color: 'var(--text-tertiary)' }} />
            </div>
            {availableModels.find(m => m.id === selectedModel)?.description && (
              <p className="text-xs mt-1.5" style={{ color: 'var(--text-tertiary)' }}>
                {availableModels.find(m => m.id === selectedModel)?.description}
              </p>
            )}
          </div>

          {/* Prompt Input */}
          <div>
            <label className="text-xs font-bold uppercase tracking-widest mb-2 block"
                   style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              Prompt
            </label>
            <div className="relative">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your image..."
                className="w-full px-4 py-3 rounded-lg focus:outline-none focus:ring-1 resize-none text-sm"
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-sans)',
                  minHeight: '100px',
                  focusRingColor: 'var(--accent)',
                }}
                rows={4}
              />
              {/* Voice prompt button */}
              <button
                onClick={handleVoicePrompt}
                className="absolute bottom-2 right-2 p-2 rounded-lg transition-all"
                style={isRecording ? {
                  background: 'var(--red)',
                  color: 'white',
                } : {
                  background: 'var(--bg-hover)',
                  color: 'var(--text-secondary)',
                }}
                title={isRecording ? 'Stop recording' : 'Speak your prompt'}
              >
                {isRecording ? <Square size={14} className="fill-current" /> : <Mic size={14} />}
              </button>
            </div>
          </div>

          {/* Advanced Settings Toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-xs uppercase tracking-widest transition-colors"
            style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
          >
            <ChevronDown
              size={14}
              style={{ transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }}
            />
            Advanced Settings
          </button>

          {showAdvanced && (
            <div className="space-y-4 p-4 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)' }}>

              {/* Negative Prompt */}
              <div>
                <label className="text-xs font-bold uppercase tracking-widest mb-1.5 block"
                       style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  Negative Prompt
                </label>
                <textarea
                  value={negativePrompt}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                  placeholder="What to exclude..."
                  className="w-full px-3 py-2 rounded-md text-sm resize-none focus:outline-none"
                  style={{
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                  }}
                  rows={2}
                />
              </div>

              {/* Steps */}
              <div>
                <label className="text-xs font-bold uppercase tracking-widest mb-1.5 block"
                       style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  Steps: {steps}
                </label>
                <input
                  type="range"
                  min={10}
                  max={50}
                  value={steps}
                  onChange={(e) => setSteps(parseInt(e.target.value))}
                  className="w-full accent-[var(--accent)]"
                />
              </div>

              {/* Size Presets */}
              <div>
                <label className="text-xs font-bold uppercase tracking-widest mb-1.5 block"
                       style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  Image Size
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {sizePresets.map(p => (
                    <button
                      key={p.label}
                      onClick={() => { setWidth(p.w); setHeight(p.h) }}
                      className="px-3 py-2 rounded-md text-xs transition-all"
                      style={{
                        background: width === p.w && height === p.h ? 'var(--accent-glow)' : 'var(--bg-primary)',
                        border: width === p.w && height === p.h ? '1px solid var(--accent)' : '1px solid var(--border)',
                        color: width === p.w && height === p.h ? 'var(--accent)' : 'var(--text-secondary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Generate Button */}
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim() || isGenerating}
            className="w-full py-4 rounded-xl font-bold uppercase tracking-wider text-sm flex items-center justify-center gap-3 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: isGenerating ? 'var(--bg-tertiary)' : 'var(--accent)',
              color: isGenerating ? 'var(--text-secondary)' : 'var(--bg-primary)',
              boxShadow: !isGenerating && prompt.trim() ? '0 0 20px var(--accent-glow)' : 'none',
              fontFamily: 'var(--font-display)',
            }}
          >
            {isGenerating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles size={18} />
                Generate Image
              </>
            )}
          </button>

          {error && (
            <div className="px-4 py-3 rounded-lg text-sm"
                 style={{ background: 'rgba(255,23,68,0.1)', border: '1px solid rgba(255,23,68,0.3)', color: 'var(--red)' }}>
              {error}
            </div>
          )}
        </div>

        {/* Right Panel: Gallery / Preview */}
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Preview Area */}
          <div className="flex-1 flex items-center justify-center p-6 overflow-auto">
            {selectedImage ? (
              <div className="max-w-full max-h-full flex flex-col items-center">
                <img
                  src={selectedImage.image}
                  alt={selectedImage.prompt}
                  className="max-w-full max-h-[65vh] rounded-xl object-contain"
                  style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.5), 0 0 1px var(--border)' }}
                />
                <div className="mt-4 text-center max-w-lg">
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    "{selectedImage.prompt}"
                  </p>
                  {selectedImage.enhanced_prompt && selectedImage.enhanced_prompt !== selectedImage.prompt && (
                    <p className="text-xs mt-1 italic" style={{ color: 'var(--text-tertiary)' }}>
                      Enhanced: {selectedImage.enhanced_prompt.substring(0, 120)}...
                    </p>
                  )}
                  <div className="flex items-center justify-center gap-4 mt-3">
                    <span className="text-xs px-2 py-0.5 rounded-full"
                          style={{ background: 'var(--accent-glow)', color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                      {selectedImage.source}
                    </span>
                    <button onClick={() => handleDownload(selectedImage)}
                            className="flex items-center gap-1 text-xs transition-colors"
                            style={{ color: 'var(--accent)' }}>
                      <Download size={12} /> Save
                    </button>
                    <button onClick={() => { setPrompt(selectedImage.prompt) }}
                            className="flex items-center gap-1 text-xs transition-colors"
                            style={{ color: 'var(--text-secondary)' }}>
                      <RefreshCw size={12} /> Reuse Prompt
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center" style={{ color: 'var(--text-tertiary)', opacity: 0.5 }}>
                <Image size={64} className="mx-auto mb-4" style={{ color: 'var(--accent)' }} />
                <p className="text-sm uppercase tracking-widest" style={{ fontFamily: 'var(--font-mono)' }}>
                  No images generated yet
                </p>
                <p className="text-xs mt-2" style={{ fontFamily: 'var(--font-mono)' }}>
                  Enter a prompt and click Generate
                </p>
              </div>
            )}
          </div>

          {/* Gallery Strip */}
          {generatedImages.length > 0 && (
            <div className="flex-shrink-0 px-4 py-3 overflow-x-auto"
                 style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
              <div className="flex gap-3">
                {generatedImages.map(img => (
                  <div
                    key={img.id}
                    onClick={() => setSelectedImage(img)}
                    className="relative flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden cursor-pointer group transition-all"
                    style={{
                      border: selectedImage?.id === img.id ? '2px solid var(--accent)' : '2px solid transparent',
                      boxShadow: selectedImage?.id === img.id ? '0 0 10px var(--accent-glow)' : 'none',
                    }}
                  >
                    <img src={img.image} alt="" className="w-full h-full object-cover" />
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(img.id) }}
                      className="absolute top-1 right-1 p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ background: 'rgba(0,0,0,0.7)', color: 'var(--red)' }}
                    >
                      <Trash2 size={10} />
                    </button>
                  </div>
                ))}
                <div ref={galleryEndRef} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
