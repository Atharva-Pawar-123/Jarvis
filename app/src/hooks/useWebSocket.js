import { useEffect, useRef } from 'react'
import useJarvisStore from '../store/useJarvisStore'

export default function useWebSocket(sessionId) {
  const wsRef = useRef(null)
  const reconnectTimeout = useRef(null)
  const retryCount = useRef(0)

  const {
    setConnected,
    setJarvisState,
    appendStreamToken,
    addAgentStep,
    clearAgentSteps,
    setPendingApproval,
    setStreaming,
    resetStream,
    updateSessionTitle,
    addMessage,
  } = useJarvisStore()

  const connect = () => {
    if (!sessionId) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const wsUrl = `ws://localhost:8080/ws/${sessionId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      retryCount.current = 0
      console.log(`[WS] Connected to session: ${sessionId}`)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case 'token':
            if (!useJarvisStore.getState().isStreaming) {
              setStreaming(true)
            }
            // Use requestAnimationFrame for smooth batch rendering
            requestAnimationFrame(() => {
              appendStreamToken(data.content)
            })
            break

          case 'state':
            setJarvisState(data.state)
            break

          case 'agent_step':
            setJarvisState('thinking')
            addAgentStep(data.step)
            break

          case 'approval_required':
            setJarvisState('thinking')
            setPendingApproval({
              request_id: data.request_id,
              action: data.action,
              details: data.details
            })
            break

          case 'complete':
            setStreaming(false)
            addMessage({
              role: 'jarvis',
              content: data.content,
              timestamp: new Date().toISOString(),
            })
            resetStream()
            setJarvisState('idle')
            break

          case 'title_update':
            updateSessionTitle(sessionId, data.title)
            break

          default:
            break
        }
      } catch (e) {
        console.error('[WS] Failed to parse message', e)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Exponential backoff reconnect
      const backoff = Math.min(1000 * Math.pow(2, retryCount.current), 30000)
      console.log(`[WS] Disconnected. Reconnecting in ${backoff}ms...`)
      reconnectTimeout.current = setTimeout(() => {
        retryCount.current += 1
        connect()
      }, backoff)
    }

    ws.onerror = () => {
      ws.close() // Trigger onclose for reconnect logic
    }
  }

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // Prevent reconnect on unmount
        wsRef.current.close()
      }
    }
  }, [sessionId])

  return wsRef.current
}
