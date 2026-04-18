import { useEffect, useRef, useState } from 'react'
import type { Sample, SamplesMessage } from './types'

// Keyed by `${service}|${metric}|${labels-json}` so each distinct timeseries is
// kept separately. Overview uses latest value; per-service tabs scan this map.
export type SampleKey = string
export const keyOf = (s: Sample): SampleKey =>
  `${s.service}|${s.metric}|${JSON.stringify(s.labels || {})}`

const MAX_HISTORY = 720 // 2h at 10s poll

export interface Streamed {
  latest: Map<SampleKey, Sample>
  history: Map<SampleKey, Sample[]>
  connected: boolean
  lastTick: string | null
}

export function usePulseStream(): Streamed {
  const [connected, setConnected] = useState(false)
  const [lastTick, setLastTick] = useState<string | null>(null)
  const latestRef = useRef(new Map<SampleKey, Sample>())
  const historyRef = useRef(new Map<SampleKey, Sample[]>())
  const [, force] = useState(0)

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimer: number | null = null
    let cancelled = false

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/api/stream`)

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!cancelled) reconnectTimer = window.setTimeout(connect, 2000)
      }
      ws.onmessage = (ev) => {
        try {
          const msg: SamplesMessage = JSON.parse(ev.data)
          ingest(msg)
        } catch {
          // ignore malformed frame
        }
      }
    }

    const ingest = (msg: SamplesMessage) => {
      for (const s of msg.samples) {
        const k = keyOf(s)
        latestRef.current.set(k, s)
        const arr = historyRef.current.get(k) ?? []
        arr.push(s)
        if (arr.length > MAX_HISTORY) arr.splice(0, arr.length - MAX_HISTORY)
        historyRef.current.set(k, arr)
      }
      if (msg.ts) setLastTick(msg.ts)
      force((n) => n + 1)
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [])

  return {
    latest: latestRef.current,
    history: historyRef.current,
    connected,
    lastTick,
  }
}
