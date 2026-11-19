import React, { useEffect, useRef } from 'react'

/**
 * HexBackground — High-performance 60fps hexagonal ambient mesh & scanlines.
 * Extracted and optimized from hud/index.html to serve as the unified sci-fi background.
 */
export default function HexBackground() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return

    let animationFrameId
    let W = (cv.width = window.innerWidth)
    let H = (cv.height = window.innerHeight)

    const handleResize = () => {
      W = cv.width = window.innerWidth
      H = cv.height = window.innerHeight
    }
    window.addEventListener('resize', handleResize)

    const R = 32
    const h = R * Math.sqrt(3)
    let cols = Math.ceil(W / (R * 3)) + 2
    let rows = Math.ceil(H / h) + 2

    // Highlights array
    const highlights = Array.from({ length: 14 }, () => ({
      col: Math.floor(Math.random() * cols),
      row: Math.floor(Math.random() * rows),
      t: Math.random() * Math.PI * 2,
      speed: 0.3 + Math.random() * 0.5,
      col_type: Math.random() < 0.7 ? 'c' : Math.random() < 0.5 ? 'v' : 'r'
    }))

    function hexPath(context, cx, cy, radius) {
      context.beginPath()
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 6
        const x = cx + radius * Math.cos(a)
        const y = cy + radius * Math.sin(a)
        i === 0 ? context.moveTo(x, y) : context.lineTo(x, y)
      }
      context.closePath()
    }

    let t = 0
    function draw() {
      ctx.clearRect(0, 0, W, H)
      cols = Math.ceil(W / (R * 3)) + 2
      rows = Math.ceil(H / h) + 2

      for (let c = 0; c < cols; c++) {
        for (let r = 0; r < rows; r++) {
          const offset = r % 2 === 0 ? 0 : R * 1.5
          const cx = -R * 1.5 + c * R * 3 + offset
          const cy = -h / 2 + r * h

          let hlAmt = 0
          let hlColor = 'c'
          for (let i = 0; i < highlights.length; i++) {
            const hl = highlights[i]
            if (hl.col === c && hl.row === r) {
              hlAmt = 0.5 + 0.5 * Math.sin(t * hl.speed + hl.t)
              hlColor = hl.col_type
              break
            }
          }

          hexPath(ctx, cx, cy, R - 1)
          if (hlAmt > 0.01) {
            const colors = {
              c: `rgba(0, 200, 255, ${0.04 + hlAmt * 0.08})`,
              v: `rgba(155, 63, 255, ${0.03 + hlAmt * 0.07})`,
              r: `rgba(255, 23, 68, ${0.03 + hlAmt * 0.06})`
            }
            ctx.fillStyle = colors[hlColor]
            ctx.fill()
            ctx.strokeStyle =
              hlColor === 'c'
                ? `rgba(0, 200, 255, ${0.1 + hlAmt * 0.15})`
                : hlColor === 'v'
                ? `rgba(155, 63, 255, ${0.08 + hlAmt * 0.12})`
                : `rgba(255, 23, 68, ${0.07 + hlAmt * 0.1})`
            ctx.lineWidth = 0.8
            ctx.stroke()
          } else {
            ctx.strokeStyle = 'rgba(0, 200, 255, 0.035)'
            ctx.lineWidth = 0.5
            ctx.stroke()
          }
        }
      }
      t += 0.012
      animationFrameId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      window.removeEventListener('resize', handleResize)
      cancelAnimationFrame(animationFrameId)
    }
  }, [])

  return (
    <>
      {/* 60fps Ambient Hexagonal Canvas */}
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none z-0"
        style={{ mixBlendMode: 'screen' }}
      />
      {/* Radial Holographic Vignette */}
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(2, 8, 16, 0.85) 100%)'
        }}
      />
      {/* Subtle CRT Holographic Scanline Overlay */}
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          background:
            'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0, 200, 255, 0.012) 3px, rgba(0, 200, 255, 0.012) 4px)'
        }}
      />
    </>
  )
}
