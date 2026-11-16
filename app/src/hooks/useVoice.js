import { useState, useRef, useCallback } from 'react'
import axios from 'axios'
import useJarvisStore from '../store/useJarvisStore'

export default function useVoice() {
  const [isRecording, setIsRecording] = useState(false)
  const [audioData, setAudioData] = useState(new Uint8Array(0))
  const mediaRecorderRef = useRef(null)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const animationFrameRef = useRef(null)

  const { setJarvisState } = useJarvisStore()

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder

      // Setup Web Audio API for waveform visualization
      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      audioContextRef.current = audioContext
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 64
      analyserRef.current = analyser

      const source = audioContext.createMediaStreamSource(stream)
      source.connect(analyser)

      mediaRecorder.start()
      setIsRecording(true)
      setJarvisState('listening')

      const updateWaveform = () => {
        if (!analyserRef.current) return
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
        analyserRef.current.getByteFrequencyData(dataArray)
        setAudioData(new Uint8Array(dataArray))
        animationFrameRef.current = requestAnimationFrame(updateWaveform)
      }
      updateWaveform()

      const chunks = []
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data)
      }

      // Return a promise that resolves with the transcribed text when stopped
      return new Promise((resolve, reject) => {
        mediaRecorder.onstop = async () => {
          cancelAnimationFrame(animationFrameRef.current)
          setAudioData(new Uint8Array(0))
          stream.getTracks().forEach((track) => track.stop())
          if (audioContextRef.current) audioContextRef.current.close()
          
          setIsRecording(false)
          setJarvisState('idle')

          const blob = new Blob(chunks, { type: 'audio/webm' })
          const formData = new FormData()
          formData.append('audio', blob, 'recording.webm')

          try {
            setJarvisState('thinking')
            const response = await axios.post('http://localhost:8080/api/voice/transcribe', formData)
            setJarvisState('idle')
            resolve(response.data.text)
          } catch (error) {
            console.error('Failed to transcribe audio:', error)
            setJarvisState('idle')
            reject(error)
          }
        }
      })
    } catch (err) {
      console.error('Microphone access denied or error:', err)
      return null
    }
  }, [setJarvisState])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
    }
  }, [isRecording])

  return { isRecording, startRecording, stopRecording, audioData }
}
