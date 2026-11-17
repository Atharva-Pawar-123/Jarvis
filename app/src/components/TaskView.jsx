import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { CheckCircle2, PlayCircle, Clock, AlertCircle, XCircle, RefreshCw, Send, ShieldAlert, RotateCcw } from 'lucide-react'

export default function TaskView() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [newGoal, setNewGoal] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const fetchTasks = async () => {
    try {
      setLoading(true)
      const res = await axios.get('http://localhost:8080/api/tasks')
      setTasks(res.data.tasks || [])
    } catch (e) {
      console.error('Failed to fetch tasks', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 4000)
    return () => clearInterval(interval)
  }, [])

  const handleCreateGoal = async (e) => {
    e.preventDefault()
    if (!newGoal.trim()) return

    try {
      setSubmitting(true)
      await axios.post('http://localhost:8080/api/workflows/goal', {
        goal: newGoal.trim()
      })
      setNewGoal('')
      fetchTasks()
    } catch (e) {
      console.error('Goal launch failed', e)
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancelTask = async (taskId) => {
    try {
      await axios.post(`http://localhost:8080/api/tasks/${taskId}/cancel`)
      fetchTasks()
    } catch (e) {
      console.error('Task cancel failed', e)
    }
  }

  const handleResumeTask = async (taskId) => {
    try {
      await axios.post(`http://localhost:8080/api/tasks/${taskId}/resume`)
      fetchTasks()
    } catch (e) {
      console.error('Task resume failed', e)
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="flex items-center gap-1 text-xs font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800"><CheckCircle2 size={12} /> COMPLETED</span>
      case 'RUNNING':
        return <span className="flex items-center gap-1 text-xs font-mono text-cyan-400 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800 animate-pulse"><PlayCircle size={12} /> RUNNING</span>
      case 'QUEUED':
        return <span className="flex items-center gap-1 text-xs font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800"><Clock size={12} /> QUEUED</span>
      case 'CANCELLED':
        return <span className="flex items-center gap-1 text-xs font-mono text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-700"><XCircle size={12} /> CANCELLED</span>
      case 'RESUMING':
        return <span className="flex items-center gap-1 text-xs font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800 animate-pulse"><RotateCcw size={12} /> RESUMING</span>
      case 'INTERRUPTED':
        return <span className="flex items-center gap-1 text-xs font-mono text-amber-500 bg-amber-950/30 px-2 py-0.5 rounded border border-amber-800"><AlertCircle size={12} /> INTERRUPTED</span>
      default:
        return <span className="flex items-center gap-1 text-xs font-mono text-rose-400 bg-rose-950/40 px-2 py-0.5 rounded border border-rose-800"><AlertCircle size={12} /> FAILED</span>
    }
  }

  return (
    <div className="flex-1 flex flex-col p-6 h-full overflow-y-auto" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div>
          <h2 className="text-xl font-bold uppercase tracking-wider"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }}>
            Autonomous Task Center
          </h2>
          <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            Goal decomposition, checkpoint persistence & subtask pipeline execution
          </p>
        </div>
        <button
          onClick={fetchTasks}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors"
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--accent)' }}
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Goal Launch Input Form */}
      <form onSubmit={handleCreateGoal} className="mb-6">
        <div className="flex items-center gap-2 p-2 rounded-xl"
             style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <input
            type="text"
            value={newGoal}
            onChange={(e) => setNewGoal(e.target.value)}
            placeholder="Assign autonomous goal (e.g. 'Audit disk usage and prepare a cleanup summary report')..."
            className="flex-1 bg-transparent px-3 py-2 text-sm focus:outline-none"
            style={{ color: 'var(--text-primary)' }}
          />
          <button
            type="submit"
            disabled={submitting || !newGoal.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold disabled:opacity-40 transition-all"
            style={{
              background: 'var(--accent)',
              color: 'var(--bg-primary)',
              boxShadow: '0 0 10px var(--accent-glow)'
            }}
          >
            <Send size={14} /> Launch Goal
          </button>
        </div>
      </form>

      {/* Tasks List */}
      <div className="space-y-4">
        {tasks.length === 0 && !loading && (
          <div className="text-center py-12 text-sm font-mono" style={{ color: 'var(--text-tertiary)' }}>
            No background autonomous tasks recorded, sir.
          </div>
        )}

        {tasks.map((task) => (
          <div
            key={task.task_id}
            className="p-5 rounded-xl transition-all"
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-start justify-between gap-4 mb-2">
              <div>
                <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                  {task.title}
                </h3>
                <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  Goal: {task.goal}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {getStatusBadge(task.status)}
                {task.status === 'RUNNING' && (
                  <button
                    onClick={() => handleCancelTask(task.task_id)}
                    className="px-2 py-0.5 rounded text-xs font-mono transition-colors text-rose-400 hover:bg-rose-950/40"
                    style={{ border: '1px solid var(--red)' }}
                  >
                    Cancel
                  </button>
                )}
                {(task.status === 'INTERRUPTED' || task.status === 'FAILED') && (
                  <button
                    onClick={() => handleResumeTask(task.task_id)}
                    className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono transition-colors text-emerald-400 hover:bg-emerald-950/40"
                    style={{ border: '1px solid var(--emerald, #10b981)' }}
                    title="Resume task from last checkpoint"
                  >
                    <RotateCcw size={11} /> Resume
                  </button>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="my-3">
              <div className="flex justify-between text-xs font-mono mb-1" style={{ color: 'var(--text-tertiary)' }}>
                <span>Step: {task.current_step}</span>
                <span>{task.progress_pct}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-tertiary)' }}>
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${task.progress_pct}%`,
                    background: task.status === 'COMPLETED' ? 'var(--emerald, #10b981)' : 'var(--accent)'
                  }}
                />
              </div>
            </div>

            {/* Deliverable Output */}
            {task.result_summary && (
              <div className="mt-3 p-3 rounded-lg text-xs font-mono max-h-40 overflow-y-auto whitespace-pre-wrap"
                   style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
                {task.result_summary}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
