import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Database, Trash2, Search, Plus, Bookmark, Brain, History, BookOpen } from 'lucide-react'

export default function MemoryView() {
  const [activeTier, setActiveTier] = useState('semantic') // working | episodic | semantic | procedural
  const [facts, setFacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [newFact, setNewFact] = useState('')
  const [newCategory, setNewCategory] = useState('general')

  useEffect(() => {
    fetchMemory()
  }, [])

  const fetchMemory = async () => {
    try {
      setLoading(true)
      const res = await axios.get('http://localhost:8080/api/memory/facts')
      setFacts(res.data.facts || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const deleteFact = async (id) => {
    try {
      await axios.delete(`http://localhost:8080/api/memory/${id}`)
      fetchMemory()
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
      fetchMemory()
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

  const filtered = searchQuery
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

      {/* Tier 3: Semantic Memory Tab */}
      {activeTier === 'semantic' && (
        <div className="space-y-4">
          {/* Add Fact Form */}
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
            {filtered.map((fact) => (
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
            ))}
          </div>
        </div>
      )}

      {/* Tier 1: Working Memory Placeholder / Explanation */}
      {activeTier === 'working' && (
        <div className="p-6 rounded-xl space-y-3 font-mono text-sm"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div className="font-bold text-accent">Active Working Memory Scratchpad</div>
          <p style={{ color: 'var(--text-secondary)' }}>
            Working memory is scoped dynamically to the active session. It maintains sub-goal decompositions,
            temporary code snippets, tool observations, and reasoning scratchpads for the active conversation turn.
          </p>
        </div>
      )}

      {/* Tier 2: Episodic Memory */}
      {activeTier === 'episodic' && (
        <div className="p-6 rounded-xl space-y-3 font-mono text-sm"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div className="font-bold text-accent">Episodic Task Timeline</div>
          <p style={{ color: 'var(--text-secondary)' }}>
            Episodic memory archives past completed autonomous task runs, goal checkpoints, and dialogue turn summaries
            chronologically in the SQLite persistence layer.
          </p>
        </div>
      )}

      {/* Tier 4: Procedural Memory */}
      {activeTier === 'procedural' && (
        <div className="p-6 rounded-xl space-y-3 font-mono text-sm"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div className="font-bold text-accent">Procedural Rules & Habits</div>
          <p style={{ color: 'var(--text-secondary)' }}>
            Procedural rules govern persona adherence (e.g. addressing sir, dry British wit),
            preferred code generation format (no explanations before code), and risk classification rules.
          </p>
        </div>
      )}
    </div>
  )
}
