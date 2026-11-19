/**
 * ImageGenView.jsx — JARVIS Image Studio Pro (Grok Imagine-Style Architecture)
 * ============================================================================
 * Seamless 3-in-1 Visual Studio:
 * 1. 🎨 Generate: Text-to-Image with multi-model local SD-Forge checkpoints.
 * 2. ✏️ Edit Canvas: Multi-session image-to-image and inpainting with mask brush,
 *    denoise slider, drag-and-drop local upload, and version lineage.
 * 3. 🖼️ Library: Full masonry asset gallery with category filter and favorites.
 * Plus Grok Imagine-style discrete session rail with 3-image preview cards.
 */

import React, { useState, useRef, useEffect } from 'react'
import {
  Sparkles,
  Download,
  Trash2,
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
  Upload,
  Paintbrush,
  RotateCcw,
  Eye,
  Check,
  Heart,
  MessageSquare,
  ChevronRight,
  FolderOpen,
  Image as ImageIcon,
  Grid,
  Edit3,
  Undo
} from 'lucide-react'
import axios from 'axios'
import useJarvisStore from '../store/useJarvisStore'

const API_BASE = 'http://localhost:8080'

export default function ImageGenView() {
  const { setActiveTab, addMessage } = useJarvisStore()

  // ── Top Mode Navigation: 'generate' | 'edit' | 'library' ──────────────
  const [activeSubTab, setActiveSubTab] = useState('generate')

  // ── Session State (Grok Imagine Multi-Session Rail) ───────────────────
  const [visualSessions, setVisualSessions] = useState([])
  const [activeVisualSessionId, setActiveVisualSessionId] = useState(null)

  // ── Common Models State ───────────────────────────────────────────────
  const [availableModels, setAvailableModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('local')
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [showEditModelMenu, setShowEditModelMenu] = useState(false)
  const [showAspectMenu, setShowAspectMenu] = useState(false)
  const [aspectRatio, setAspectRatio] = useState('1:1')
  const [width, setWidth] = useState(512)
  const [height, setHeight] = useState(512)

  // ── Generate Mode State ───────────────────────────────────────────────
  const [generatePrompt, setGeneratePrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [steps, setSteps] = useState(20)

  // ── Edit Canvas State ─────────────────────────────────────────────────
  const [editPrompt, setEditPrompt] = useState('')
  const [initImage, setInitImage] = useState(null) // base64 or URL
  const [maskImage, setMaskImage] = useState(null)
  const [denoisingStrength, setDenoisingStrength] = useState(0.65)
  const [isEditing, setIsEditing] = useState(false)
  const [editError, setEditError] = useState('')
  const [brushSize, setBrushSize] = useState(24)
  const [isMaskingMode, setIsMaskingMode] = useState(false)
  const [canvasVersions, setCanvasVersions] = useState([]) // [ { id, image, prompt } ]

  // ── Library Mode State ────────────────────────────────────────────────
  const [libraryAssets, setLibraryAssets] = useState([])
  const [libraryFilter, setLibraryFilter] = useState('all') // 'all' | 'generated' | 'uploaded' | 'edited' | 'favorite'
  const [librarySearch, setLibrarySearch] = useState('')
  const [previewModalAsset, setPreviewModalAsset] = useState(null)

  // ── Refs ──────────────────────────────────────────────────────────────
  const fileInputRef = useRef(null)
  const canvasRef = useRef(null)
  const modelMenuRef = useRef(null)
  const editModelMenuRef = useRef(null)
  const aspectMenuRef = useRef(null)
  const isDrawingRef = useRef(false)

  // ── Close popups when clicking outside ────────────────────────────────
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target)) {
        setShowModelMenu(false)
      }
      if (editModelMenuRef.current && !editModelMenuRef.current.contains(e.target)) {
        setShowEditModelMenu(false)
      }
      if (aspectMenuRef.current && !aspectMenuRef.current.contains(e.target)) {
        setShowAspectMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // ── Aspect Ratio Options ──────────────────────────────────────────────
  const aspectRatios = [
    { id: '1:1', label: '1:1 Square', sd: [512, 512], flux: [1024, 1024] },
    { id: '4:5', label: '4:5 Portrait', sd: [512, 640], flux: [896, 1152] },
    { id: '9:16', label: '9:16 Mobile', sd: [512, 768], flux: [768, 1344] },
    { id: '16:9', label: '16:9 Cinema', sd: [768, 512], flux: [1344, 768] },
    { id: '3:2', label: '3:2 Landscape', sd: [768, 512], flux: [1152, 768] }
  ]

  // ── Lifecycle: Fetch on Mount ─────────────────────────────────────────
  useEffect(() => {
    fetchModels()
    fetchVisualSessions()
    fetchLibrary()
  }, [])

  // ── Data Fetchers ─────────────────────────────────────────────────────
  const fetchModels = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/image/models`)
      const models = res.data.models || []
      setAvailableModels(models)
      if (models.length > 0 && !models.some((m) => m.id === selectedModel)) {
        setSelectedModel(models[0].id)
      }
    } catch {
      setAvailableModels([
        { id: 'local', name: 'DreamShaper 8 (Local SD 1.5)', category: 'SD1.5' }
      ])
    }
  }

  const fetchVisualSessions = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/image/sessions`)
      const list = res.data.sessions || []
      setVisualSessions(list)
      if (list.length > 0 && !activeVisualSessionId) {
        loadVisualSession(list[0].session_id)
      }
    } catch (e) {
      console.warn('Failed to fetch visual sessions', e)
    }
  }

  const loadVisualSession = async (sid) => {
    try {
      setActiveVisualSessionId(sid)
      const res = await axios.get(`${API_BASE}/api/image/sessions/${sid}`)
      const sess = res.data
      if (sess && sess.assets) {
        const formatted = sess.assets.map((a) => ({
          id: a.id,
          image: a.image_base64 ? `data:image/png;base64,${a.image_base64}` : (a.filepath || ''),
          prompt: a.prompt,
          type: a.asset_type
        }))
        setCanvasVersions(formatted)
        if (formatted.length > 0) {
          setInitImage(formatted[formatted.length - 1].image)
        }
      }
    } catch (e) {
      console.warn('Failed to load visual session', e)
    }
  }

  const handleCreateNewSession = async () => {
    try {
      const res = await axios.post(`${API_BASE}/api/image/sessions/new`, {
        title: `Imagine Session ${visualSessions.length + 1}`,
        mode: activeSubTab
      })
      const newSess = res.data
      setVisualSessions((prev) => [newSess, ...prev])
      setActiveVisualSessionId(newSess.session_id)
      setCanvasVersions([])
      setInitImage(null)
      setMaskImage(null)
    } catch (e) {
      console.error('Failed to create visual session', e)
    }
  }

  const fetchLibrary = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/image/library`, {
        params: {
          type: libraryFilter === 'favorite' ? 'all' : libraryFilter,
          favorite: libraryFilter === 'favorite'
        }
      })
      setLibraryAssets(res.data.assets || [])
    } catch (e) {
      console.warn('Failed to fetch library', e)
    }
  }

  // ── Upload Handler from Computer Storage ──────────────────────────────
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)
    if (activeVisualSessionId) {
      formData.append('session_id', activeVisualSessionId)
    }

    try {
      const res = await axios.post(`${API_BASE}/api/image/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const uploadedDataUrl = `data:image/png;base64,${res.data.image_base64}`
      setInitImage(uploadedDataUrl)
      setCanvasVersions((prev) => [
        ...prev,
        { id: res.data.id, image: uploadedDataUrl, prompt: file.name, type: 'uploaded' }
      ])
      // Switch automatically to edit tab so user can immediately edit their uploaded photo!
      setActiveSubTab('edit')
      fetchVisualSessions()
      fetchLibrary()
    } catch (err) {
      console.error('File upload failed', err)
    }
  }

  // ── Generation Handler (Text to Image) ────────────────────────────────
  const handleGenerate = async () => {
    if (!generatePrompt.trim() || isGenerating) return
    setIsGenerating(true)

    try {
      const res = await axios.post(`${API_BASE}/api/image/generate`, {
        prompt: generatePrompt.trim(),
        negative_prompt: negativePrompt.trim(),
        model: selectedModel,
        steps: steps,
        width: width,
        height: height,
        session_id: activeVisualSessionId
      })

      const dataUrl = `data:image/png;base64,${res.data.image_base64}`
      setCanvasVersions((prev) => [
        ...prev,
        { id: res.data.id || Date.now(), image: dataUrl, prompt: generatePrompt, type: 'generated' }
      ])
      setInitImage(dataUrl)
      fetchVisualSessions()
      fetchLibrary()
    } catch (err) {
      console.error('Generation error', err)
    }
    setIsGenerating(false)
  }

  // ── Edit Handler (Image to Image / Inpainting) ─────────────────────────
  const handleEdit = async () => {
    if (!editPrompt.trim() || !initImage || isEditing) return
    setIsEditing(true)
    setEditError('')

    try {
      const res = await axios.post(`${API_BASE}/api/image/edit`, {
        init_image: initImage,
        prompt: editPrompt.trim(),
        mask_image: maskImage,
        denoising_strength: denoisingStrength,
        model: selectedModel,
        steps: steps,
        session_id: activeVisualSessionId
      })

      const dataUrl = `data:image/png;base64,${res.data.image_base64}`
      setCanvasVersions((prev) => [
        ...prev,
        { id: res.data.id, image: dataUrl, prompt: editPrompt, type: 'edited' }
      ])
      setInitImage(dataUrl)
      setMaskImage(null)
      fetchVisualSessions()
      fetchLibrary()
    } catch (err) {
      console.error('Edit error', err)
      const detail = err.response?.data?.detail || 'SD Forge engine is offline or loading. Please start SD Forge on port 7860.'
      setEditError(detail)
    }
    setIsEditing(false)
  }

  // ── Inpaint Mask Drawing Logic ────────────────────────────────────────
  const startDrawing = (e) => {
    if (!isMaskingMode || !canvasRef.current) return
    isDrawingRef.current = true
    draw(e)
  }

  const stopDrawing = () => {
    if (!isDrawingRef.current || !canvasRef.current) return
    isDrawingRef.current = false
    setMaskImage(canvasRef.current.toDataURL('image/png'))
  }

  const draw = (e) => {
    if (!isDrawingRef.current || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    ctx.fillStyle = 'white'
    ctx.beginPath()
    ctx.arc(x, y, brushSize, 0, Math.PI * 2)
    ctx.fill()
  }

  const clearMask = () => {
    if (!canvasRef.current) return
    const ctx = canvasRef.current.getContext('2d')
    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
    setMaskImage(null)
  }

  // ── Send to Chat (Chat with Image via LLaVA) ──────────────────────────
  const handleSendToChat = (imgUrl) => {
    addMessage({
      role: 'user',
      content: 'I have attached an image from Image Studio for inspection.',
      timestamp: new Date().toISOString()
    })
    addMessage({
      role: 'jarvis',
      content: `I have received the image from your studio session, sir. What would you like me to analyze or assist you with regarding this image?`,
      timestamp: new Date().toISOString()
    })
    setActiveTab('chat')
  }

  return (
    <div className="flex h-full w-full bg-[#050C16] text-slate-100 overflow-hidden font-sans select-none">
      {/* ═══════════════════════════════════════════════════════════════════
          LEFT: GROK IMAGINE-STYLE SESSION RAIL (Thumbnails + Session Cards)
      ═══════════════════════════════════════════════════════════════════════ */}
      <aside className="w-64 border-r border-cyan-500/20 bg-[#071322] flex flex-col shrink-0">
        <div className="p-3 border-b border-cyan-500/20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
              IMAGINE SESSIONS
            </span>
          </div>
          <button
            onClick={handleCreateNewSession}
            className="p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 transition-all text-xs flex items-center gap-1"
            title="New Canvas Session"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {visualSessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-500 font-mono">
              No sessions yet. Start imagining!
            </div>
          ) : (
            visualSessions.map((sess) => {
              const isActive = sess.session_id === activeVisualSessionId
              return (
                <div
                  key={sess.session_id}
                  onClick={() => loadVisualSession(sess.session_id)}
                  className={`p-2.5 rounded-xl border cursor-pointer transition-all ${
                    isActive
                      ? 'border-cyan-400/80 bg-cyan-950/40 shadow-[0_0_12px_rgba(0,200,255,0.15)]'
                      : 'border-slate-800/80 hover:border-slate-700 bg-slate-900/40'
                  }`}
                >
                  {/* Miniature Cards Preview (Grok 3-image miniature strip) */}
                  <div className="grid grid-cols-3 gap-1 mb-2 h-14 rounded-lg overflow-hidden bg-slate-950/60 p-0.5 border border-slate-800">
                    {sess.thumbnails && sess.thumbnails.length > 0 ? (
                      sess.thumbnails.map((t, idx) => (
                        <div key={idx} className="w-full h-full bg-slate-800 relative overflow-hidden rounded">
                          <img
                            src={t.filepath?.startsWith('data:') ? t.filepath : `${API_BASE}/${t.filepath}`}
                            alt="preview"
                            className="w-full h-full object-cover"
                            onError={(e) => { e.target.style.display = 'none' }}
                          />
                        </div>
                      ))
                    ) : (
                      <div className="col-span-3 flex items-center justify-center text-[10px] text-slate-600 font-mono">
                        Empty Canvas
                      </div>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-200 truncate">
                      {sess.title || 'Visual Session'}
                    </span>
                    <span className="text-[10px] text-cyan-400/70 font-mono">
                      {sess.asset_count || 0} imgs
                    </span>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </aside>

      {/* ═══════════════════════════════════════════════════════════════════
          CENTER/RIGHT: MAIN STUDIO VIEWPORT
      ═══════════════════════════════════════════════════════════════════════ */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        {/* Top Header & Sub-Tabs Navigation */}
        <header className="h-14 border-b border-cyan-500/20 bg-[#071322]/80 backdrop-blur px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-cyan-500/20">
            <button
              onClick={() => setActiveSubTab('generate')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeSubTab === 'generate'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,200,255,0.2)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Generate
            </button>
            <button
              onClick={() => setActiveSubTab('edit')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeSubTab === 'edit'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,200,255,0.2)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Edit3 className="w-3.5 h-3.5" />
              Edit Canvas
            </button>
            <button
              onClick={() => {
                setActiveSubTab('library')
                fetchLibrary()
              }}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeSubTab === 'library'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,200,255,0.2)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Grid className="w-3.5 h-3.5" />
              Library
            </button>
          </div>

          {/* Hidden File Input for Local Computer Storage Upload */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
          />

          {/* Right Header Controls */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs font-medium transition-all shadow-[0_0_8px_rgba(0,200,255,0.1)]"
            >
              <Upload className="w-3.5 h-3.5" />
              Upload Image
            </button>
          </div>
        </header>

        {/* ── SUB-TAB 1: GENERATE (PROMPT TO IMAGE) ───────────────────── */}
        {activeSubTab === 'generate' && (
          <div className="flex-1 flex flex-col relative overflow-hidden items-center justify-center p-6">
            {/* Main Stage Preview */}
            <div className="flex-1 w-full max-w-4xl flex items-center justify-center relative mb-24">
              {initImage ? (
                <div className="relative rounded-2xl overflow-hidden border border-cyan-500/30 shadow-[0_0_30px_rgba(0,200,255,0.15)] max-h-[70vh] group">
                  <img src={initImage} alt="Generated" className="object-contain max-h-[70vh] rounded-2xl" />
                  <div className="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleSendToChat(initImage)}
                      className="p-2 rounded-lg bg-black/60 backdrop-blur text-cyan-300 hover:bg-black/90 border border-cyan-500/30"
                      title="Chat with Image"
                    >
                      <MessageSquare className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setActiveSubTab('edit')}
                      className="p-2 rounded-lg bg-black/60 backdrop-blur text-cyan-300 hover:bg-black/90 border border-cyan-500/30"
                      title="Edit this Image"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <a
                      href={initImage}
                      download="jarvis_imagine.png"
                      className="p-2 rounded-lg bg-black/60 backdrop-blur text-cyan-300 hover:bg-black/90 border border-cyan-500/30"
                      title="Download"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center text-center p-8 max-w-md border border-dashed border-cyan-500/20 rounded-2xl">
                  <Sparkles className="w-12 h-12 text-cyan-400 mb-3 animate-pulse" />
                  <h3 className="text-base font-semibold text-slate-200 mb-1">What should we imagine?</h3>
                  <p className="text-xs text-slate-400">
                    Type a prompt below or upload an image to begin creative synthesis.
                  </p>
                </div>
              )}
            </div>

            {/* Floating Bottom Console (Grok Imagine Style) */}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 z-20">
              <div className="bg-[#0A182E]/90 backdrop-blur-md border border-cyan-500/30 rounded-2xl p-3 shadow-[0_8px_32px_rgba(0,0,0,0.5)] flex flex-col gap-2">
                <textarea
                  value={generatePrompt}
                  onChange={(e) => setGeneratePrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleGenerate()
                    }
                  }}
                  placeholder="Type to imagine anything..."
                  rows={2}
                  className="w-full bg-transparent resize-none border-none outline-none text-sm text-slate-100 placeholder:text-slate-500 px-2"
                />

                {/* Control Pills Bar */}
                <div className="flex items-center justify-between pt-1 border-t border-cyan-500/15 text-xs">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="p-1.5 rounded-lg hover:bg-cyan-500/10 text-cyan-400"
                      title="Upload local image"
                    >
                      <Plus className="w-4 h-4" />
                    </button>

                    {/* Model Picker Pill */}
                    <div className="relative" ref={modelMenuRef}>
                      <button
                        onClick={() => setShowModelMenu(!showModelMenu)}
                        className="px-2.5 py-1 rounded-lg bg-slate-900 border border-cyan-500/20 text-cyan-300 font-mono text-[11px] flex items-center gap-1.5"
                      >
                        <Cpu className="w-3 h-3" />
                        {availableModels.find((m) => m.id === selectedModel)?.name || 'Local SD'}
                      </button>
                      {showModelMenu && (
                        <div className="absolute bottom-8 left-0 w-64 bg-slate-900 border border-cyan-500/30 rounded-xl p-1 shadow-2xl z-30">
                          {availableModels.map((m) => (
                            <div
                              key={m.id}
                              onClick={() => {
                                setSelectedModel(m.id)
                                setShowModelMenu(false)
                              }}
                              className="p-2 rounded-lg hover:bg-cyan-500/15 cursor-pointer text-xs"
                            >
                              <div className="font-semibold text-slate-200">{m.name}</div>
                              <div className="text-[10px] text-slate-400">{m.category}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Aspect Ratio Pill */}
                    <div className="relative" ref={aspectMenuRef}>
                      <button
                        onClick={() => setShowAspectMenu(!showAspectMenu)}
                        className="px-2.5 py-1 rounded-lg bg-slate-900 border border-cyan-500/20 text-cyan-300 font-mono text-[11px] flex items-center gap-1.5"
                      >
                        <Crop className="w-3 h-3" />
                        {aspectRatio}
                      </button>
                      {showAspectMenu && (
                        <div className="absolute bottom-8 left-0 w-44 bg-slate-900 border border-cyan-500/30 rounded-xl p-1 shadow-2xl z-30">
                          {aspectRatios.map((r) => (
                            <div
                              key={r.id}
                              onClick={() => {
                                setAspectRatio(r.id)
                                setWidth(r.sd[0])
                                setHeight(r.sd[1])
                                setShowAspectMenu(false)
                              }}
                              className="p-2 rounded-lg hover:bg-cyan-500/15 cursor-pointer text-xs flex items-center justify-between"
                            >
                              <span className="text-slate-200">{r.label}</span>
                              <span className="text-[10px] text-cyan-400 font-mono">{r.sd[0]}x{r.sd[1]}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating || !generatePrompt.trim()}
                    className="px-5 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs transition-all shadow-[0_0_12px_rgba(0,200,255,0.4)] disabled:opacity-40 disabled:shadow-none flex items-center gap-1.5"
                  >
                    {isGenerating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    Imagine
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── SUB-TAB 2: EDIT CANVAS (IMAGE-TO-IMAGE & INPAINTING) ─────── */}
        {activeSubTab === 'edit' && (
          <div className="flex-1 flex flex-col relative overflow-hidden items-center justify-center p-6">
            {/* Version Lineage Breadcrumbs Bar */}
            {canvasVersions.length > 0 && (
              <div className="absolute top-4 left-6 flex items-center gap-1.5 z-10 bg-slate-900/80 backdrop-blur px-3 py-1.5 rounded-xl border border-cyan-500/20 text-xs font-mono">
                <span className="text-slate-400">Lineage:</span>
                {canvasVersions.map((v, i) => (
                  <button
                    key={v.id}
                    onClick={() => setInitImage(v.image)}
                    className="px-2 py-0.5 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  >
                    v{i + 1}
                  </button>
                ))}
              </div>
            )}

            {/* Central Canvas Viewport */}
            <div className="flex-1 w-full max-w-4xl flex items-center justify-center relative mb-24">
              {/* Error Banner if SD Forge is offline */}
              {editError && (
                <div className="absolute top-4 inset-x-8 bg-red-950/80 border border-red-500/40 text-red-200 px-4 py-2.5 rounded-xl backdrop-blur-md z-30 flex items-center justify-between text-xs font-mono shadow-xl animate-fade-in">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-400 animate-ping" />
                    <span>{editError}</span>
                  </div>
                  <button
                    onClick={() => setEditError('')}
                    className="p-1 rounded hover:bg-red-900/60 text-red-400"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {initImage ? (
                <div className="relative rounded-2xl overflow-hidden border border-cyan-500/30 shadow-[0_0_30px_rgba(0,200,255,0.15)] max-h-[65vh]">
                  <img src={initImage} alt="Base for edit" className="object-contain max-h-[65vh] rounded-2xl" />
                  {/* Overlay Canvas for Mask Inpainting */}
                  {isMaskingMode && (
                    <canvas
                      ref={canvasRef}
                      width={512}
                      height={512}
                      onMouseDown={startDrawing}
                      onMouseUp={stopDrawing}
                      onMouseMove={draw}
                      className="absolute inset-0 w-full h-full cursor-crosshair opacity-60 bg-red-500/10"
                    />
                  )}
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="flex flex-col items-center justify-center text-center p-12 max-w-md border-2 border-dashed border-cyan-500/30 hover:border-cyan-400/60 rounded-2xl cursor-pointer transition-all bg-cyan-950/10"
                >
                  <Upload className="w-12 h-12 text-cyan-400 mb-3" />
                  <h3 className="text-sm font-semibold text-slate-200 mb-1">Upload an image to start editing</h3>
                  <p className="text-xs text-slate-400">Click or drag & drop any image from your computer</p>
                </div>
              )}
            </div>

            {/* Floating Edit Console */}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 z-20">
              <div className="bg-[#0A182E]/90 backdrop-blur-md border border-cyan-500/30 rounded-2xl p-3 shadow-[0_8px_32px_rgba(0,0,0,0.5)] flex flex-col gap-2">
                <textarea
                  value={editPrompt}
                  onChange={(e) => setEditPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleEdit()
                    }
                  }}
                  placeholder="Describe your edits: e.g., 'Turn this into an oil painting', 'Add sunglasses'..."
                  rows={2}
                  className="w-full bg-transparent resize-none border-none outline-none text-sm text-slate-100 placeholder:text-slate-500 px-2"
                />

                {/* Edit Controls Pills */}
                <div className="flex items-center justify-between pt-1 border-t border-cyan-500/15 text-xs">
                  <div className="flex items-center gap-2">
                    {/* Model Picker Pill in Edit Mode */}
                    <div className="relative" ref={editModelMenuRef}>
                      <button
                        onClick={() => setShowEditModelMenu(!showEditModelMenu)}
                        className="px-2.5 py-1 rounded-lg bg-slate-900 border border-cyan-500/20 text-cyan-300 font-mono text-[11px] flex items-center gap-1.5"
                      >
                        <Cpu className="w-3 h-3" />
                        {availableModels.find((m) => m.id === selectedModel)?.name || 'Local SD'}
                      </button>
                      {showEditModelMenu && (
                        <div className="absolute bottom-8 left-0 w-64 bg-slate-900 border border-cyan-500/30 rounded-xl p-1 shadow-2xl z-30">
                          {availableModels.map((m) => (
                            <div
                              key={m.id}
                              onClick={() => {
                                setSelectedModel(m.id)
                                setShowEditModelMenu(false)
                              }}
                              className="p-2 rounded-lg hover:bg-cyan-500/15 cursor-pointer text-xs"
                            >
                              <div className="font-semibold text-slate-200">{m.name}</div>
                              <div className="text-[10px] text-slate-400">{m.category}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Denoise Strength Slider */}
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-cyan-500/20 text-cyan-300 font-mono text-[11px]">
                      <span>Denoise: {denoisingStrength}</span>
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={denoisingStrength}
                        onChange={(e) => setDenoisingStrength(parseFloat(e.target.value))}
                        className="w-16 accent-cyan-400"
                      />
                    </div>

                    {/* Mask Brush Toggle */}
                    <button
                      onClick={() => setIsMaskingMode(!isMaskingMode)}
                      className={`px-2.5 py-1 rounded-lg border font-mono text-[11px] flex items-center gap-1.5 transition-all ${
                        isMaskingMode
                          ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                          : 'bg-slate-900 border-cyan-500/20 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Paintbrush className="w-3 h-3" />
                      Brush Mask
                    </button>

                    {isMaskingMode && (
                      <button
                        onClick={clearMask}
                        className="px-2 py-1 rounded-lg bg-red-500/20 text-red-300 text-[11px] border border-red-500/30"
                      >
                        Clear Mask
                      </button>
                    )}
                  </div>

                  <button
                    onClick={handleEdit}
                    disabled={isEditing || !editPrompt.trim() || !initImage}
                    className="px-5 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs transition-all shadow-[0_0_12px_rgba(0,200,255,0.4)] disabled:opacity-40 disabled:shadow-none flex items-center gap-1.5"
                  >
                    {isEditing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Edit3 className="w-3.5 h-3.5" />}
                    Apply Edit
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── SUB-TAB 3: ASSET LIBRARY (MASONRY GALLERY) ──────────────── */}
        {activeSubTab === 'library' && (
          <div className="flex-1 flex flex-col p-6 overflow-y-auto">
            {/* Filter Bar */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-cyan-500/20">
              <div className="flex items-center gap-2">
                {['all', 'generated', 'uploaded', 'edited', 'favorite'].map((f) => (
                  <button
                    key={f}
                    onClick={() => {
                      setLibraryFilter(f)
                      fetchLibrary()
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                      libraryFilter === f
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                        : 'text-slate-400 hover:text-slate-200 bg-slate-900/60'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {/* Masonry Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {libraryAssets.length === 0 ? (
                <div className="col-span-full text-center py-12 text-slate-500 text-sm">
                  No images in library matching your filter.
                </div>
              ) : (
                libraryAssets.map((asset) => {
                  const imgUrl = asset.image_base64
                    ? `data:image/png;base64,${asset.image_base64}`
                    : (asset.filepath || '')
                  return (
                    <div
                      key={asset.id}
                      className="group relative rounded-xl overflow-hidden border border-slate-800 hover:border-cyan-500/50 transition-all bg-slate-900/40"
                    >
                      <img src={imgUrl} alt={asset.prompt} className="w-full h-44 object-cover" />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity p-2.5 flex flex-col justify-end">
                        <p className="text-[11px] text-slate-200 line-clamp-2 mb-2">{asset.prompt}</p>
                        <div className="flex items-center justify-between">
                          <button
                            onClick={() => {
                              setInitImage(imgUrl)
                              setActiveSubTab('edit')
                            }}
                            className="p-1 rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/40"
                            title="Edit this Image"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <a
                            href={imgUrl}
                            download={`jarvis_asset_${asset.id}.png`}
                            className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700"
                            title="Download"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
