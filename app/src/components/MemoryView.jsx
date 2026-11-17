import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Database, Trash2, Search, Plus, Bookmark, Brain, History, BookOpen, RefreshCw, CheckCircle, Clock } from 'lucide-react'

export default function MemoryView() {
  const [activeTier, setActiveTier] = useState('semantic') // working | episodic | semantic | procedural
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Semantic state
  const [facts, setFacts] = useState([])
  const [newFact, setNewFact] = useState('')
  const [newCategory, setNewCategory] = useState('general')

  // Working state
  const [workingState, setWorkingState] = useState(null)

  // Episodic state
  const [episodes, setEpisodes] = useState([])

  // Procedural state
  const [proceduralRules, setProceduralRules] = useState([])
  const [newRuleKey, setNewRuleKey] = useState('')
  const [newRuleCategory, setNewRuleCategory] = useState('persona')
  const [newRuleText, setNewRuleText] = useState('')

  useEffect(() => {
    fetchActiveTierData()
  }, [activeTier])

  const fetchActiveTierData = async () => {
    setLoading(true)
    try {
      if (activeTier === 'semantic') {
        const res = await axios.get('http://localhost:8080/api/memory/facts')
        setFacts(res.data.facts || [])
      } else if (activeTier === 'working') {
        const res = await axios.get('http://localhost:8080/api/memory/working')
        setWorkingState(res.data || null)
      } else if (activeTier === 'episodic') {
        const res = await axios.get('http://localhost:8080/api/memory/episodic')
        setEpisodes(res.data.episodes || [])
      } else if (activeTier === 'procedural') {
        const res = await axios.get('http://localhost:8080/api/memory/procedural')
        setProceduralRules(res.data.preferences || [])
      }
    } catch (e) {
      console.error('Failed to load memory tier data:', e)
    } finally {
      setLoading(false)
    }
  }

  // --- Semantic Actions ---
  const deleteFact = async (id) => {
    try {
      await axios.delete(`http://localhost:8080/api/memory/${id}`)
      fetchActiveTierData()
    } catch (e) {
      console.error(e)
    }
  }

  const handleAddFact = async (e) => {
    e.preventDefault()
    if (!newFact.trim()) return
    try {
      await axios.post('http://localhost:8080/api/memory/add', {
        fact: newFact.trim(),
        category: newCategory
      })
      setNewFact('')
      fetchActiveTierData()
    } catch (e) {
      console.error(e)
    }
  }

  // --- Episodic Actions ---
  const deleteEpisode = async (id) => {
    try {
      await axios.delete(`http://localhost:8080/api/memory/episodic/${id}`)
      fetchActiveTierData()
    } catch (e) {
      console.error(e)
    }
  }

  // --- Procedural Actions ---
  const handleAddProceduralRule = async (e) => {
    e.preventDefault()
    if (!newRuleText.trim()) return
    const key = newRuleKey.trim() || `rule_${Date.now()}`
    try {
      await axios.post('http://localhost:8080/api/memory/procedural', {
        key: key,
        category: newRuleCategory,
        preference: newRuleText.trim()
      })
      setNewRuleKey('')
      setNewRuleText('')
      fetchActiveTierData()
    } catch (e) {
      console.error(e)
    }
  }

  const deleteProceduralRule = async (key) => {
    try {
      await axios.delete(`http://localhost:8080/api/memory/procedural/${encodeURIComponent(key)}`)
      fetchActiveTierData()
    } catch (e) {
      console.error(e)
    }
  }

  const tiers = [
    { id: 'working', label: '1. Working Memory', icon: Brain, desc: 'Active session scratchpad & context' },
    { id: 'episodic', label: '2. Episodic Memory', icon: History, desc: 'Chronological timeline of task episodes' },
    { id: 'semantic', label: '3. Semantic Memory', icon: Database, desc: 'Vectorized facts & knowledge bank' },
    { id: 'procedural', label: '4. Procedural Memory', icon: BookOpen, desc: 'Learned user preferences & behavioral habits' },
  ]

  const filteredFacts = searchQuery
    ? facts.filter(f => f.text.toLowerCase().includes(searchQuery.toLowerCase()))
    : facts

  return (
    <div className="flex-1 flex flex-col p-6 h-full overflow-y-auto" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div>
          <h2 className="text-xl font-bold uppercase tracking-wider"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
            4-Tier Cognitive Memory Architecture
          </h2>
          <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            Integrated Working, Episodic, Semantic (ChromaDB), and Procedural Knowledge
          </p>
        </div>
        <button
          onClick={fetchActiveTierData}
          className="p-2 rounded-xl text-xs flex items-center gap-1.5 font-mono"
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          title="Refresh memory tier"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Tier Selector Navigation */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {tiers.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTier(t.id)}
            className="p-3 rounded-xl text-left transition-all"
            style={{
              background: activeTier === t.id ? 'var(--accent-glow)' : 'var(--bg-secondary)',
              border: activeTier === t.id ? '1px solid var(--accent)' : '1px solid var(--border)',
              color: activeTier === t.id ? 'var(--accent)' : 'var(--text-secondary)'
            }}
          >
            <div className="flex items-center gap-2 mb-1">
              <t.icon size={16} />
              <span className="font-semibold text-xs tracking-wider uppercase font-mono">{t.label}</span>
            </div>
            <p className="text-xs opacity-75 line-clamp-1">{t.desc}</p>
          </button>
        ))}
      </div>

      {/* Tier 1: Working Memory Tab */}
      {activeTier === 'working' && (
        <div className="space-y-4 font-mono text-sm">
          <div className="p-4 rounded-xl space-y-3"
               style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
            <div className="font-bold flex items-center gap-2" style={{ color: 'var(--accent)' }}>
              <Brain size={16} /> Active Working Memory Context
            </div>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Working memory is dynamically injected into each reasoning loop. It combines procedural rules,
              recent episodic outcomes, and active session constraints.
            </p>
            {workingState ? (
              <div className="space-y-3 pt-2">
                <div className="flex gap-4 text-xs">
                  <div className="p-2.5 rounded-lg flex-1" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                    <div className="text-xs uppercase opacity-60">Active Rules Count</div>
                    <div className="text-lg font-bold" style={{ color: 'var(--accent)' }}>{workingState.procedural_rules_count}</div>
                  </div>
                  <div className="p-2.5 rounded-lg flex-1" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)' }}>
                    <div className="text-xs uppercase opacity-60">Recent Episodes</div>
                    <div className="text-lg font-bold" style={{ color: 'var(--accent)' }}>{workingState.recent_episodes_count}</div>
                  </div>
                </div>
                {workingState.active_rules?.length > 0 && (
                  <div>
                    <div className="text-xs font-bold uppercase mb-2 opacity-80">Loaded Behavioral Constraints:</div>
                    <ul className="list-disc list-inside space-y-1 text-xs opacity-90">
                      {workingState.active_rules.map((r, idx) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs opacity-50 py-4">No active working memory scratchpad found.</div>
            )}
          </div>
        </div>
      )}

      {/* Tier 2: Episodic Memory Tab */}
      {activeTier === 'episodic' && (
        <div className="space-y-4">
          <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            Chronological log of completed reasoning loops, tasks, and tool execution outcomes.
          </div>
          {episodes.length === 0 ? (
            <div className="p-8 text-center text-xs font-mono opacity-50 rounded-xl"
                 style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
              No recorded episodes yet. Tasks completed by JARVIS will appear here.
            </div>
          ) : (
            <div className="space-y-3">
              {episodes.map((ep) => {
                let parsedTools = []
                try {
                  parsedTools = JSON.parse(ep.tools_used || '[]')
                } catch {
                  parsedTools = []
                }
                return (
                  <div
                    key={ep.episode_id}
                    className="group p-4 rounded-xl flex justify-between items-start gap-4 transition-all"
                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-2 py-0.5 rounded font-mono font-bold"
                              style={{ background: 'var(--accent-glow)', color: 'var(--accent)' }}>
                          Episode #{ep.episode_id}
                        </span>
                        <span className="text-xs font-mono opacity-50 flex items-center gap-1">
                          <Clock size={12} /> {new Date(ep.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Goal: {ep.user_goal}
                      </div>
                      <div className="text-xs opacity-80 leading-relaxed font-mono" style={{ color: 'var(--text-secondary)' }}>
                        Outcome: {ep.outcome}
                      </div>
                      {parsedTools.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {parsedTools.map((t, idx) => (
                            <span key={idx} className="text-[10px] font-mono px-2 py-0.5 rounded"
                                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--accent)' }}>
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => deleteEpisode(ep.episode_id)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded transition-opacity"
                      style={{ color: 'var(--red)' }}
                      title="Delete episode"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tier 3: Semantic Memory Tab */}
      {activeTier === 'semantic' && (
        <div className="space-y-4">
          <form onSubmit={handleAddFact} className="flex gap-2">
            <input
              type="text"
              placeholder="Store a permanent memory fact (e.g. 'Sir prefers concise executive summaries')..."
              value={newFact}
              onChange={(e) => setNewFact(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-xl text-sm focus:outline-none"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="px-3 py-2 rounded-xl text-xs font-mono"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            >
              <option value="general">General</option>
              <option value="preference">Preference</option>
              <option value="hardware">Hardware</option>
              <option value="project">Project</option>
            </select>
            <button
              type="submit"
              className="px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5"
              style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
            >
              <Plus size={14} /> Add Fact
            </button>
          </form>

          {/* Search Bar */}
          <div className="flex items-center gap-2 rounded-xl px-4 py-2.5"
               style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
            <Search size={16} style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Search facts across semantic ChromaDB..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent border-none focus:outline-none text-xs font-mono"
              style={{ color: 'var(--text-primary)' }}
            />
          </div>

          {/* Facts List */}
          <div className="space-y-2 mt-4">
            {filteredFacts.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono opacity-50 rounded-xl"
                   style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                No semantic facts stored yet.
              </div>
            ) : (
              filteredFacts.map((fact) => (
                <div
                  key={fact.id}
                  className="group p-3.5 rounded-xl flex justify-between items-start gap-4 transition-all"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                >
                  <div className="flex-1 text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                    {fact.text}
                    {fact.category && (
                      <span className="ml-2 text-xs px-2 py-0.5 rounded-full font-mono uppercase"
                            style={{ background: 'var(--accent-glow)', color: 'var(--accent)' }}>
                        {fact.category}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => deleteFact(fact.id)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded transition-opacity"
                    style={{ color: 'var(--red)' }}
                    title="Delete memory"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tier 4: Procedural Memory Tab */}
      {activeTier === 'procedural' && (
        <div className="space-y-4">
          <form onSubmit={handleAddProceduralRule} className="p-4 rounded-xl space-y-3"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
            <div className="font-bold text-xs uppercase tracking-wider font-mono" style={{ color: 'var(--accent)' }}>
              Add Procedural Habit or Behavioral Rule
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input
                type="text"
                placeholder="Key (e.g. 'code_style', 'tone')"
                value={newRuleKey}
                onChange={(e) => setNewRuleKey(e.target.value)}
                className="px-3 py-2 rounded-xl text-xs font-mono focus:outline-none"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              />
              <select
                value={newRuleCategory}
                onChange={(e) => setNewRuleCategory(e.target.value)}
                className="px-3 py-2 rounded-xl text-xs font-mono"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              >
                <option value="persona">Persona / Tone</option>
                <option value="code_style">Code Formatting</option>
                <option value="safety">Safety / Permissions</option>
                <option value="workflow">Workflow Habit</option>
              </select>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              >
                <Plus size={14} /> Save Preference
              </button>
            </div>
            <textarea
              placeholder="Detailed preference rule (e.g. 'Always address user as sir; generate production-ready code with no fluff')..."
              value={newRuleText}
              onChange={(e) => setNewRuleText(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-xl text-xs font-mono focus:outline-none"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </form>

          {/* Procedural Rules List */}
          <div className="space-y-2 mt-4">
            {proceduralRules.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono opacity-50 rounded-xl"
                   style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                No procedural rules defined yet.
              </div>
            ) : (
              proceduralRules.map((rule) => (
                <div
                  key={rule.key}
                  className="group p-3.5 rounded-xl flex justify-between items-start gap-4 transition-all"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                >
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-xs" style={{ color: 'var(--accent)' }}>
                        {rule.key}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-mono uppercase"
                            style={{ background: 'var(--accent-glow)', color: 'var(--accent)' }}>
                        {rule.category}
                      </span>
                    </div>
                    <div className="text-xs font-mono leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                      {rule.preference}
                    </div>
                  </div>
                  <button
                    onClick={() => deleteProceduralRule(rule.key)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded transition-opacity"
                    style={{ color: 'var(--red)' }}
                    title="Delete rule"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
