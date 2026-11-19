import React, { useEffect, useRef } from 'react'

/**
 * ArcReactorCanvas — Authentic Iron Man rotating Arc Reactor Canvas with dynamic HUD telemetry
 * Directly ported from hud/index.html and responsive to CPU/GPU activity.
 */
export default function ArcReactorCanvas({ activeLoad = 0, size = 380 }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return

    let animationFrameId
    const W = (cv.width = size)
    const H = (cv.height = size)
    const cx = W / 2
    const cy = H / 2
    const maxR = size * 0.44

    let sweep = 0
    let spin1 = 0
    let spin2 = 0

    function glow(color, blur) {
      ctx.shadowBlur = blur
      ctx.shadowColor = color
    }
    function noGlow() {
      ctx.shadowBlur = 0
    }

    function drawRing(r, alpha, dash, lw, colorType = 'c') {
      const color = colorType === 'c' ? `rgba(0,200,255,${alpha})` : `rgba(155,63,255,${alpha})`
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.strokeStyle = color
      ctx.lineWidth = lw || 1
      glow(color, 8)
      ctx.setLineDash(dash || [])
      ctx.stroke()
      ctx.setLineDash([])
      noGlow()
    }

    function drawTicks(r, n, longEvery, len, shortLen) {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI * 2
        const isLong = i % longEvery === 0
        const r1 = r - (isLong ? len : shortLen)
        ctx.beginPath()
        ctx.moveTo(cx + r1 * Math.cos(a), cy + r1 * Math.sin(a))
        ctx.lineTo(cx + (r + 2) * Math.cos(a), cy + (r + 2) * Math.sin(a))
        ctx.strokeStyle = isLong ? 'rgba(0,200,255,0.85)' : 'rgba(0,200,255,0.25)'
        ctx.lineWidth = isLong ? 1.5 : 0.6
        glow('rgba(0,200,255,0.4)', isLong ? 5 : 0)
        ctx.stroke()
        noGlow()
      }
    }

    function drawRadarSweep() {
      for (let i = 0; i < 16; i++) {
        const a = sweep - (i * Math.PI) / 20
        const op = ((16 - i) / 16) * 0.06
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.arc(cx, cy, maxR * 0.95, a - Math.PI / 20, a)
        ctx.closePath()
        ctx.fillStyle = `rgba(0,200,255,${op})`
        ctx.fill()
      }
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(sweep)
      ctx.beginPath()
      ctx.moveTo(0, 0)
      ctx.lineTo(maxR * 0.95, 0)
      ctx.strokeStyle = 'rgba(0,200,255,0.8)'
      ctx.lineWidth = 1.2
      glow('rgba(0,200,255,0.9)', 12)
      ctx.stroke()
      noGlow()
      ctx.restore()
    }

    function drawSpinRing(r, angle, dash, colorType, alpha, lw) {
      const color = colorType === 'c' ? `rgba(0,200,255,${alpha})` : `rgba(155,63,255,${alpha})`
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(angle)
      ctx.beginPath()
      ctx.arc(0, 0, r, 0, Math.PI * 2)
      ctx.strokeStyle = color
      ctx.lineWidth = lw || 1
      ctx.setLineDash(dash)
      glow(color, 6)
      ctx.stroke()
      ctx.setLineDash([])
      noGlow()
      ctx.restore()
    }

    function drawArcReactor() {
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60)
      grd.addColorStop(0, 'rgba(0,200,255,0.22)')
      grd.addColorStop(0.4, 'rgba(155,63,255,0.1)')
      grd.addColorStop(1, 'transparent')
      ctx.beginPath()
      ctx.arc(cx, cy, 60, 0, Math.PI * 2)
      ctx.fillStyle = grd
      ctx.fill()

      // Outer hexagon
      ctx.beginPath()
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i + Math.PI / 6
        const x = cx + 48 * Math.cos(a)
        const y = cy + 48 * Math.sin(a)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.strokeStyle = 'rgba(0,200,255,0.7)'
      ctx.lineWidth = 1.2
      glow('rgba(0,200,255,0.8)', 8)
      ctx.stroke()
      noGlow()
      ctx.fillStyle = 'rgba(0,200,255,0.05)'
      ctx.fill()

      // Triangular segments inside hexagon
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i + Math.PI / 6
        const a2 = (Math.PI / 3) * (i + 1) + Math.PI / 6
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(cx + 48 * Math.cos(a), cy + 48 * Math.sin(a))
        ctx.lineTo(cx + 48 * Math.cos(a2), cy + 48 * Math.sin(a2))
        ctx.closePath()
        ctx.strokeStyle = i % 2 === 0 ? 'rgba(0,200,255,0.25)' : 'rgba(155,63,255,0.2)'
        ctx.lineWidth = 0.6
        ctx.stroke()
      }

      // Inner triangle (classic arc reactor)
      ctx.beginPath()
      for (let i = 0; i < 3; i++) {
        const a = ((Math.PI * 2) / 3) * i - Math.PI / 2
        const x = cx + 24 * Math.cos(a)
        const y = cy + 24 * Math.sin(a)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.strokeStyle = 'rgba(0,200,255,0.85)'
      ctx.lineWidth = 1.4
      glow('rgba(0,200,255,0.9)', 10)
      ctx.stroke()
      noGlow()
      ctx.fillStyle = 'rgba(0,200,255,0.1)'
      ctx.fill()

      // Center Core
      const cgrd = ctx.createRadialGradient(cx, cy, 0, cx, cy, 12)
      cgrd.addColorStop(0, '#ffffff')
      cgrd.addColorStop(0.3, 'rgba(0,200,255,0.9)')
      cgrd.addColorStop(1, 'rgba(0,200,255,0.1)')
      ctx.beginPath()
      ctx.arc(cx, cy, 12, 0, Math.PI * 2)
      glow('rgba(0,200,255,1)', 24)
      ctx.fillStyle = cgrd
      ctx.fill()
      noGlow()

      // Violet inner ring accent
      ctx.beginPath()
      ctx.arc(cx, cy, 32, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(155,63,255,0.4)'
      ctx.lineWidth = 1
      glow('rgba(155,63,255,0.4)', 6)
      ctx.stroke()
      noGlow()
    }

    function frame() {
      ctx.clearRect(0, 0, W, H)
      drawRadarSweep()

      // Rings
      drawRing(maxR, 0.75, [], 1.5, 'c')
      drawTicks(maxR, 48, 6, 10, 4)
      drawSpinRing(maxR * 0.82, spin1, [3, 7], 'c', 0.45)
      drawRing(maxR * 0.67, 0.45, [2, 5], 0.8, 'v')
      drawSpinRing(maxR * 0.52, spin2, [4, 6], 'c', 0.4)
      drawRing(maxR * 0.38, 0.65, [], 1.2, 'c')
      drawArcReactor()

      // Red/Cyan warning accent arc
      ctx.beginPath()
      ctx.arc(cx, cy, maxR * 0.92, -Math.PI / 8, Math.PI / 8)
      ctx.strokeStyle = activeLoad > 75 ? 'rgba(255,23,68,0.7)' : 'rgba(0,200,255,0.5)'
      ctx.lineWidth = 2
      glow(activeLoad > 75 ? 'rgba(255,23,68,0.8)' : 'rgba(0,200,255,0.6)', 8)
      ctx.stroke()
      noGlow()

      const speedFactor = 1 + (activeLoad / 100) * 1.5
      sweep += 0.02 * speedFactor
      spin1 += 0.007 * speedFactor
      spin2 -= 0.011 * speedFactor

      animationFrameId = requestAnimationFrame(frame)
    }

    frame()

    return () => {
      cancelAnimationFrame(animationFrameId)
    }
  }, [activeLoad, size])

  return (
    <div className="relative flex items-center justify-center">
      <canvas ref={canvasRef} width={size} height={size} className="drop-shadow-[0_0_24px_rgba(0,200,255,0.3)]" />
    </div>
  )
}
