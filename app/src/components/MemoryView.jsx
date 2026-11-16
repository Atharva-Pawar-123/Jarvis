import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Database, Trash2, Search, Plus } from 'lucide-react'

export default function MemoryView() {
  const [facts, setFacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

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

  const filtered = searchQuery
    ? facts.filter(f => f.text.toLowerCase().includes(searchQuery.toLowerCase()))
    : facts

  return (
    <div className="flex-1 flex flex-col p-8 h-full overflow-y-auto" style={{ background: 'var(--bg-primary)' }}>
      <div className="flex items-center gap-3 mb-6">
        <Database style={{ color: 'var(--accent)' }} size={28} />
        <h2 className="text-2xl font-bold uppercase tracking-wider"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
          Semantic Memory Core
        </h2>
      </div>

      {/* Search Bar */}
      <div className="flex items-center gap-2 mb-6 rounded-xl px-4 py-3 max-w-2xl"
           style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
        <Search size={18} style={{ color: 'var(--text-tertiary)' }} />
        <input
          type="text"
          placeholder="Search memory banks..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 bg-transparent border-none focus:outline-none text-sm"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}
        />
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>Accessing databanks...</div>
      ) : (
        <div className="space-y-3 max-w-3xl">
          <div className="text-xs font-bold uppercase tracking-widest mb-2"
               style={{ color: 'var(--text-tertiary)' }}>
            {filtered.length} {filtered.length === 1 ? 'Memory' : 'Memories'} Found
          </div>
          {filtered.length === 0 ? (
            <div className="italic" style={{ color: 'var(--text-tertiary)' }}>Memory banks are empty.</div>
          ) : (
            filtered.map((fact) => (
              <div key={fact.id}
                   className="group p-4 rounded-xl flex justify-between items-start gap-4 transition-all"
                   style={{
                     background: 'var(--bg-secondary)',
                     border: '1px solid var(--border)',
                   }}>
                <div className="flex-1 leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                  {fact.text}
                  {fact.category && (
                    <span className="ml-2 text-xs px-2 py-0.5 rounded-full"
                          style={{ background: 'var(--accent-glow)', color: 'var(--accent)' }}>
                      {fact.category}
                    </span>
                  )}
                </div>
                <button 
                  onClick={() => deleteFact(fact.id)}
                  className="opacity-0 group-hover:opacity-100 p-2 rounded-lg transition-all"
                  style={{ color: 'var(--red)' }}
                  title="Purge Memory"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
