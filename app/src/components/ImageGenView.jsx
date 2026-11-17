/**
 * ImageGenView.jsx — Modern Studio & Generation Console
 * ====================================================
 * Modern bottom floating bar interface inspired by Midjourney/SeaArt/Higgsfield:
 * - Floating bottom console with integrated text prompt and quick control pills:
 *   [+] [@] [Model Selector Dropdown] [Aspect Ratio Pill] [Quality / Steps] [Resolution] [Batch 1] [Generate Button]
 * - Rich searchable popup model menu with badges (LOCAL, FLUX, SD1.5, CLOUD, FAST) and descriptions.
 * - Expansive central canvas preview with full zoom/inspection and prompt metadata.
 * - Bottom/side image history strip.
 */

import React, { useState, useRef, useEffect } from 'react'
import {
  Image as ImageIcon,
  Sparkles,
  Download,
  Trash2,
  Mic,
  Square,
  Loader2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Search,
  Sliders,
  Crop,
  Layers,
  Cpu,
  Zap,
  Globe,
  Maximize2,
  X,
  Plus,
  AtSign
} from 'lucide-react'
import axios from 'axios'

import useVoice from '../hooks/useVoice'

const API_BASE = 'http://localhost:8080'

export default function ImageGenView() {
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [selectedModel, setSelectedModel] = useState('local')
  const [availableModels, setAvailableModels] = useState([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedImages, setGeneratedImages] = useState([])
  const [steps, setSteps] = useState(20)
  const [width, setWidth] = useState(512)
  const [height, setHeight] = useState(512)
  const [aspectRatio, setAspectRatio] = useState('1:1')
  const [error, setError] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)
  
  // UI popup states
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [showAspectMenu, setShowAspectMenu] = useState(false)
  const [showQualityMenu, setShowQualityMenu] = useState(false)
  const [showSettingsDrawer, setShowSettingsDrawer] = useState(false)
  const [modelSearchQuery, setModelSearchQuery] = useState('')

  const modelMenuRef = useRef(null)
  const aspectMenuRef = useRef(null)
  const qualityMenuRef = useRef(null)
  const textareaRef = useRef(null)

  const { isRecording, startRecording, stopRecording } = useVoice()

  // Fetch available models on mount
  useEffect(() => {
    fetchModels()
  }, [])

  // Close popups on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target)) {
        setShowModelMenu(false)
      }
      if (aspectMenuRef.current && !aspectMenuRef.current.contains(e.target)) {
        setShowAspectMenu(false)
      }
      if (qualityMenuRef.current && !qualityMenuRef.current.contains(e.target)) {
        setShowQualityMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchModels = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/image/models`)
      const models = res.data.models || []
      setAvailableModels(models)
      if (models.length > 0 && !models.some(m => m.id === selectedModel)) {
        handleModelSelect(models[0])
      }
    } catch {
      const fallbackList = [
        { id: 'local', name: 'DreamShaper 8', source: 'forge', category: 'SD1.5', description: 'Local SD Forge — High speed on NVIDIA RTX GPU', default_steps: 20, default_dim: 512 },
        { id: 'pollinations:flux', name: 'FLUX.1 Schnell', source: 'pollinations', category: 'FLUX', description: 'Exceptional open-weights photorealism (4 steps)', default_steps: 4, default_dim: 1024 },
        { id: 'pollinations:flux-realism', name: 'FLUX Realism', source: 'pollinations', category: 'FLUX', description: 'Tuned for realistic skin, portraiture & textures', default_steps: 4, default_dim: 1024 },
        { id: 'pollinations:flux-anime', name: 'FLUX Anime', source: 'pollinations', category: 'Cloud', description: 'Stylized anime, concept art, and digital illustrations', default_steps: 4, default_dim: 1024 },
        { id: 'pollinations:turbo', name: 'Pollinations Turbo', source: 'pollinations', category: 'Cloud', description: 'Fast generation with clean prompt adherence', default_steps: 20, default_dim: 512 },
      ]
      setAvailableModels(fallbackList)
    }
  }

  const handleModelSelect = (model) => {
    setSelectedModel(model.id)
    setShowModelMenu(false)
    if (model.default_steps) setSteps(model.default_steps)
    
    // Adjust dimension according to model architecture family
    const isFlux = (model.category === 'FLUX' || model.id.toLowerCase().includes('flux'))
    updateDimensionsForAspect(aspectRatio, isFlux)
  }

  const aspectRatios = [
    { id: '1:1', label: '1:1 Square', icon: '■', sd: [512, 512], flux: [1024, 1024] },
    { id: '4:5', label: '4:5 Portrait', icon: '▮', sd: [512, 640], flux: [896, 1152] },
    { id: '9:16', label: '9:16 Mobile', icon: '▯', sd: [512, 768], flux: [768, 1344] },
    { id: '16:9', label: '16:9 Cinema', icon: '▭', sd: [768, 512], flux: [1344, 768] },
    { id: '3:2', label: '3:2 Landscape', icon: '▬', sd: [768, 512], flux: [1152, 768] },
  ]

  const updateDimensionsForAspect = (ratioId, isFluxModel = null) => {
    setAspectRatio(ratioId)
    const activeM = availableModels.find(m => m.id === selectedModel)
    const isFlux = isFluxModel !== null ? isFluxModel : (activeM?.category === 'FLUX' || selectedModel.toLowerCase().includes('flux'))
    
    const targetRatio = aspectRatios.find(r => r.id === ratioId) || aspectRatios[0]
    const dims = isFlux ? targetRatio.flux : targetRatio.sd
    setWidth(dims[0])
    setHeight(dims[1])
  }

  const handleAspectSelect = (ratioId) => {
    updateDimensionsForAspect(ratioId)
    setShowAspectMenu(false)
  }

  const handleGenerate = async () => {
    if (!prompt.trim() || isGenerating) return
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
      }, { timeout: 180000 })

      if (res.data.image_base64) {
        const newImage = {
          id: Date.now(),
          prompt: prompt.trim(),
          image: `data:image/png;base64,${res.data.image_base64}`,
          source: res.data.source || 'Unknown',
          filepath: res.data.filepath || '',
          timestamp: new Date().toISOString(),
          enhanced_prompt: res.data.enhanced_prompt || '',
          width,
          height,
          model: selectedModel,
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
          setPrompt(prev => prev ? `${prev} ${text.trim()}` : text.trim())
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

  const currentModelObj = availableModels.find(m => m.id === selectedModel) || {
    name: selectedModel,
    category: selectedModel.includes('local') ? 'LOCAL' : 'CLOUD',
  }

  const filteredModels = availableModels.filter(m =>
    m.name.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
    (m.description && m.description.toLowerCase().includes(modelSearchQuery.toLowerCase())) ||
    (m.category && m.category.toLowerCase().includes(modelSearchQuery.toLowerCase()))
  )

  return (
    <div className="flex flex-col h-full w-full overflow-hidden relative select-none" style={{ background: '#080A0F' }}>
      
      {/* ── Top Header Navigation Bar ───────────────────────────────── */}
      <div className="flex items-center justify-between px-6 py-3 z-10"
           style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.06)', background: 'rgba(10, 14, 22, 0.85)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shadow-lg"
               style={{ background: 'linear-gradient(135deg, #00C8FF 0%, #0077FF 100%)' }}>
            <Sparkles size={18} className="text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-wider uppercase text-white" style={{ fontFamily: 'var(--font-display)' }}>
                Image Studio
              </h1>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-mono uppercase tracking-widest font-semibold"
                    style={{ background: 'rgba(0, 200, 255, 0.15)', color: '#00C8FF', border: '1px solid rgba(0, 200, 255, 0.3)' }}>
                Offline-First Pro
              </span>
            </div>
            <p className="text-[11px] text-gray-400">
              High-fidelity local & distributed diffusion synthesis
            </p>
          </div>
        </div>

        {/* Top Right Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowSettingsDrawer(!showSettingsDrawer)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-all"
            style={{
              background: showSettingsDrawer ? 'rgba(0, 200, 255, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              border: showSettingsDrawer ? '1px solid #00C8FF' : '1px solid rgba(255, 255, 255, 0.1)',
              color: showSettingsDrawer ? '#00C8FF' : '#94A3B8'
            }}
          >
            <Sliders size={13} />
            <span>Parameters</span>
          </button>
        </div>
      </div>

      {/* ── Main Viewport (Preview & Gallery) ───────────────────────── */}
      <div className="flex-1 flex overflow-hidden relative">

        {/* Canvas Display */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 pb-36 overflow-auto relative">
          {selectedImage ? (
            <div className="flex flex-col items-center justify-center max-w-full max-h-full transition-all duration-300">
              <div className="relative group rounded-2xl overflow-hidden shadow-2xl border border-white/10"
                   style={{ maxHeight: 'calc(100vh - 280px)' }}>
                <img
                  src={selectedImage.image}
                  alt={selectedImage.prompt}
                  className="max-h-[calc(100vh-280px)] w-auto object-contain rounded-2xl select-none"
                  style={{ boxShadow: '0 20px 60px rgba(0,0,0,0.8)' }}
                />

                {/* Quick overlay actions */}
                <div className="absolute top-3 right-3 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                  <button
                    onClick={() => handleDownload(selectedImage)}
                    className="p-2 rounded-xl backdrop-blur-md bg-black/60 text-white hover:bg-black/90 transition-all border border-white/10"
                    title="Download PNG"
                  >
                    <Download size={15} />
                  </button>
                  <button
                    onClick={() => handleDelete(selectedImage.id)}
                    className="p-2 rounded-xl backdrop-blur-md bg-black/60 text-red-400 hover:bg-black/90 transition-all border border-white/10"
                    title="Remove from session"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>

                <div className="absolute bottom-3 left-3 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                  <span className="text-[11px] px-2.5 py-1 rounded-lg backdrop-blur-md bg-black/70 text-gray-200 border border-white/10 font-mono">
                    {selectedImage.width}×{selectedImage.height}
                  </span>
                  <span className="text-[11px] px-2.5 py-1 rounded-lg backdrop-blur-md bg-cyan-950/80 text-cyan-300 border border-cyan-500/30 font-mono">
                    {selectedImage.source}
                  </span>
                </div>
              </div>

              {/* Prompt Bar below active image */}
              <div className="mt-3 flex items-center gap-3 max-w-xl text-center px-4">
                <p className="text-xs text-gray-300 font-sans line-clamp-1 italic">
                  "{selectedImage.prompt}"
                </p>
                <button
                  onClick={() => setPrompt(selectedImage.prompt)}
                  className="flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors font-mono whitespace-nowrap"
                >
                  <RefreshCw size={11} /> Reuse
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center max-w-md mx-auto p-8 rounded-2xl border border-white/5 bg-white/[0.01]">
              <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 shadow-inner">
                <ImageIcon size={28} />
              </div>
              <h3 className="text-base font-semibold text-white tracking-wide mb-1" style={{ fontFamily: 'var(--font-display)' }}>
                Creative Canvas Empty
              </h3>
              <p className="text-xs text-gray-400 leading-relaxed font-sans mb-4">
                Describe any scene or portrait in the bottom console below. Pick your local or cloud model and press Generate.
              </p>
              <div className="flex flex-wrap items-center justify-center gap-2">
                {['Cyberpunk Tokyo rainy alley 8k octane', 'Hyperrealistic portrait of an astronaut', 'Vintage comic book mech artwork'].map(suggestion => (
                  <button
                    key={suggestion}
                    onClick={() => setPrompt(suggestion)}
                    className="text-[11px] px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 transition-all font-sans"
                  >
                    "{suggestion}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* History Filmstrip at Top Right or Bottom */}
          {generatedImages.length > 0 && (
            <div className="absolute top-4 left-6 flex items-center gap-2 max-w-md overflow-x-auto py-1 px-1 rounded-xl bg-black/40 backdrop-blur-md border border-white/10">
              {generatedImages.map(img => (
                <div
                  key={img.id}
                  onClick={() => setSelectedImage(img)}
                  className={`w-12 h-12 rounded-lg overflow-hidden cursor-pointer flex-shrink-0 transition-all border ${
                    selectedImage?.id === img.id ? 'border-cyan-400 ring-2 ring-cyan-400/30' : 'border-transparent opacity-60 hover:opacity-100'
                  }`}
                >
                  <img src={img.image} alt="" className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Side Advanced Settings Drawer (Optional) ─────────────── */}
        {showSettingsDrawer && (
          <div className="w-80 border-l border-white/10 p-5 space-y-6 overflow-y-auto z-20"
               style={{ background: 'rgba(12, 16, 26, 0.95)', backdropFilter: 'blur(16px)' }}>
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-widest text-cyan-400 font-mono">
                Engine Parameters
              </h4>
              <button onClick={() => setShowSettingsDrawer(false)} className="text-gray-400 hover:text-white">
                <X size={16} />
              </button>
            </div>

            {/* Negative Prompt */}
            <div>
              <label className="text-[11px] uppercase tracking-wider text-gray-400 font-mono mb-2 block">
                Negative Prompt (Exclusions)
              </label>
              <textarea
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="ugly, blurry, lowres, distorted, extra limbs..."
                className="w-full px-3 py-2 text-xs rounded-xl bg-black/50 border border-white/10 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-400 resize-none h-20"
              />
            </div>

            {/* Steps Slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-[11px] uppercase tracking-wider text-gray-400 font-mono">
                  Sampling Steps
                </label>
                <span className="text-xs font-mono font-bold text-cyan-400">{steps}</span>
              </div>
              <input
                type="range"
                min={1}
                max={50}
                value={steps}
                onChange={(e) => setSteps(parseInt(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer"
              />
              <p className="text-[10px] text-gray-500 mt-1 font-mono">
                {currentModelObj.category === 'FLUX' ? 'Recommended 4 steps for Schnell models' : 'Recommended 20-30 steps for standard checkpoints'}
              </p>
            </div>

            {/* Exact Resolution */}
            <div>
              <label className="text-[11px] uppercase tracking-wider text-gray-400 font-mono mb-2 block">
                Exact Dimensions
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-black/50 border border-white/10 rounded-xl px-3 py-2">
                  <span className="text-[10px] text-gray-500 font-mono block">WIDTH</span>
                  <input
                    type="number"
                    value={width}
                    onChange={(e) => setWidth(parseInt(e.target.value) || 512)}
                    className="w-full bg-transparent text-sm font-mono text-white focus:outline-none"
                  />
                </div>
                <div className="bg-black/50 border border-white/10 rounded-xl px-3 py-2">
                  <span className="text-[10px] text-gray-500 font-mono block">HEIGHT</span>
                  <input
                    type="number"
                    value={height}
                    onChange={(e) => setHeight(parseInt(e.target.value) || 512)}
                    className="w-full bg-transparent text-sm font-mono text-white focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Modern Floating Bottom Bar (Higgsfield / SeaArt style) ───── */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[94%] max-w-4xl z-30">
        
        {/* Error notification if any */}
        {error && (
          <div className="mb-2 px-4 py-2 rounded-xl text-xs flex items-center justify-between text-red-200 border border-red-500/30 bg-red-950/80 backdrop-blur-md">
            <span>{error}</span>
            <button onClick={() => setError('')}><X size={14} /></button>
          </div>
        )}

        {/* ── Floating Console Card ─────────────────────────────────── */}
        <div className="rounded-2xl p-3 border shadow-2xl transition-all"
             style={{
               background: 'rgba(23, 27, 34, 0.96)',
               backdropFilter: 'blur(20px)',
               borderColor: 'rgba(255, 255, 255, 0.1)',
               boxShadow: '0 16px 48px rgba(0, 0, 0, 0.8), 0 0 1px rgba(255, 255, 255, 0.2)'
             }}>
          
          {/* Main Input Textarea */}
          <div className="px-3 pt-1">
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe the scene you imagine..."
              className="w-full bg-transparent text-white placeholder-gray-500 text-sm focus:outline-none resize-none leading-relaxed"
              rows={2}
              style={{ fontFamily: 'var(--font-sans)' }}
            />
          </div>

          {/* Lower Control Bar with Pills & Action Button */}
          <div className="flex items-center justify-between pt-2 px-1 border-t border-white/5 gap-2">
            
            {/* Left Pill Group */}
            <div className="flex items-center gap-1.5 flex-wrap">
              
              {/* Voice / Mic dictation pill */}
              <button
                onClick={handleVoicePrompt}
                className={`p-2 rounded-xl transition-all border ${
                  isRecording
                    ? 'bg-red-500/20 text-red-400 border-red-500 animate-pulse'
                    : 'bg-white/[0.04] text-gray-400 hover:text-white border-white/5'
                }`}
                title={isRecording ? 'Stop dictation' : 'Voice prompt'}
              >
                {isRecording ? <Square size={14} className="fill-current" /> : <Mic size={14} />}
              </button>

              {/* Model Picker Pill (Trigger with Chevron) */}
              <div className="relative" ref={modelMenuRef}>
                <button
                  onClick={() => setShowModelMenu(!showModelMenu)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-white/10 text-white text-xs font-medium transition-all"
                >
                  {currentModelObj.category === 'LOCAL' || currentModelObj.category === 'SD1.5' ? (
                    <Cpu size={14} className="text-emerald-400" />
                  ) : currentModelObj.category === 'FLUX' ? (
                    <Zap size={14} className="text-amber-400" />
                  ) : (
                    <Globe size={14} className="text-cyan-400" />
                  )}
                  <span className="font-semibold text-gray-100 max-w-[140px] truncate">
                    {currentModelObj.name}
                  </span>
                  <ChevronDown size={14} className="text-gray-400" />
                </button>

                {/* ── Modern Model Dropdown Menu ────────────────────────── */}
                {showModelMenu && (
                  <div className="absolute bottom-full left-0 mb-3 w-80 rounded-2xl p-2.5 border shadow-2xl z-50 overflow-hidden"
                       style={{
                         background: 'rgba(16, 20, 29, 0.98)',
                         backdropFilter: 'blur(25px)',
                         borderColor: 'rgba(255, 255, 255, 0.12)',
                         boxShadow: '0 20px 50px rgba(0, 0, 0, 0.9)'
                       }}>
                    
                    {/* Search inside popup */}
                    <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-black/50 border border-white/10 mb-2">
                      <Search size={14} className="text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search models..."
                        value={modelSearchQuery}
                        onChange={(e) => setModelSearchQuery(e.target.value)}
                        className="bg-transparent text-xs text-white placeholder-gray-500 focus:outline-none w-full"
                        autoFocus
                      />
                    </div>

                    <div className="px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-gray-500 font-semibold">
                      Featured & Local Models
                    </div>

                    {/* Model List */}
                    <div className="max-h-64 overflow-y-auto space-y-1 pr-1">
                      {filteredModels.map((m) => {
                        const isSelected = m.id === selectedModel
                        const isFlux = m.category === 'FLUX' || m.id.toLowerCase().includes('flux')
                        const isLocal = m.source === 'forge' || m.id.startsWith('local')

                        return (
                          <div
                            key={m.id}
                            onClick={() => handleModelSelect(m)}
                            className={`flex items-start gap-3 p-2.5 rounded-xl cursor-pointer transition-all ${
                              isSelected
                                ? 'bg-cyan-500/15 border border-cyan-500/30 text-white'
                                : 'hover:bg-white/[0.05] border border-transparent text-gray-300'
                            }`}
                          >
                            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                                 style={{
                                   background: isLocal
                                     ? 'rgba(16, 185, 129, 0.15)'
                                     : isFlux
                                     ? 'rgba(245, 158, 11, 0.15)'
                                     : 'rgba(0, 200, 255, 0.15)',
                                   color: isLocal ? '#34D399' : isFlux ? '#FBBF24' : '#00C8FF'
                                 }}>
                              {isLocal ? <Cpu size={14} /> : isFlux ? <Zap size={14} /> : <Globe size={14} />}
                            </div>

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold truncate text-white">
                                  {m.name}
                                </span>
                                {isLocal && (
                                  <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 font-mono font-bold">
                                    LOCAL
                                  </span>
                                )}
                                {isFlux && (
                                  <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono font-bold">
                                    FLUX
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-gray-400 line-clamp-1 mt-0.5">
                                {m.description || 'Ready for generation'}
                              </p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Aspect Ratio Pill */}
              <div className="relative" ref={aspectMenuRef}>
                <button
                  onClick={() => setShowAspectMenu(!showAspectMenu)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-white/10 text-white text-xs font-mono transition-all"
                  title="Canvas Aspect Ratio"
                >
                  <Crop size={13} className="text-gray-400" />
                  <span>{aspectRatio}</span>
                </button>

                {showAspectMenu && (
                  <div className="absolute bottom-full left-0 mb-3 w-48 rounded-xl p-1.5 border shadow-2xl z-50 bg-[#10141D] border-white/10">
                    {aspectRatios.map((r) => (
                      <div
                        key={r.id}
                        onClick={() => handleAspectSelect(r.id)}
                        className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-xs font-mono ${
                          aspectRatio === r.id ? 'bg-cyan-500/20 text-cyan-300' : 'text-gray-300 hover:bg-white/5'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <span>{r.icon}</span>
                          <span>{r.label}</span>
                        </span>
                        <span className="text-[10px] text-gray-500">{r.id}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Resolution / Steps Pill */}
              <button
                onClick={() => setShowSettingsDrawer(!showSettingsDrawer)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-white/10 text-gray-300 text-xs font-mono transition-all"
                title="Current Dimensions"
              >
                <span>{width}×{height}</span>
              </button>

              {/* Quality / Steps badge */}
              <button
                onClick={() => setShowSettingsDrawer(true)}
                className="hidden sm:flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-white/[0.04] text-gray-400 border border-white/5 text-xs font-mono"
              >
                <span>{steps} steps</span>
              </button>
            </div>

            {/* Right Action: Vibrant Accent Generate Button (Lime / Cyan) */}
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || isGenerating}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold uppercase tracking-wider text-xs transition-all disabled:opacity-40 disabled:cursor-not-allowed select-none shadow-lg"
              style={{
                background: isGenerating
                  ? '#1F2937'
                  : 'linear-gradient(135deg, #CCFF00 0%, #A6E200 100%)',
                color: isGenerating ? '#9CA3AF' : '#000000',
                boxShadow: !isGenerating && prompt.trim()
                  ? '0 0 20px rgba(204, 255, 0, 0.35)'
                  : 'none',
                fontFamily: 'var(--font-display)',
              }}
            >
              {isGenerating ? (
                <>
                  <Loader2 size={15} className="animate-spin text-gray-300" />
                  <span>CREATING...</span>
                </>
              ) : (
                <>
                  <Sparkles size={14} className="fill-black" />
                  <span>GENERATE</span>
                </>
              )}
            </button>

          </div>
        </div>
      </div>

    </div>
  )
}