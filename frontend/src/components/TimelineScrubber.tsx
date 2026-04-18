import { useEffect, useMemo, useState } from 'react'
import { fetchRange } from '@/api/range'
import type { Sample, Status } from '@/api/types'

interface Props {
  service: string | null  // null = all services (Overview)
  onPick: (ts: string | null) => void
  pickedTs: string | null
}

const WINDOWS = [
  { label: '15m', minutes: 15 },
  { label: '1h',  minutes: 60 },
  { label: '6h',  minutes: 360 },
  { label: '24h', minutes: 1440 },
  { label: '7d',  minutes: 10080 },
]

const statusColor: Record<Status, string> = {
  green: 'var(--green)',
  amber: 'var(--amber)',
  red: 'var(--red)',
  unknown: 'var(--unknown)',
}

export function TimelineScrubber({ service, onPick, pickedTs }: Props) {
  const [minutes, setMinutes] = useState(60)
  const [samples, setSamples] = useState<Sample[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchRange(service, minutes)
      .then((s) => { if (!cancelled) setSamples(s) })
      .catch((e) => { if (!cancelled) setError(String(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [service, minutes])

  // Bucket samples into N columns, colour each bucket by its worst status.
  const buckets = useMemo(() => {
    const N = 180
    const now = Date.now()
    const start = now - minutes * 60_000
    const size = Math.max(1, (now - start) / N)
    const out: { worst: Status; ts: number; count: number }[] = Array.from(
      { length: N }, (_, i) => ({ worst: 'unknown', ts: start + i * size, count: 0 }),
    )
    const rank: Record<Status, number> = { unknown: 0, green: 1, amber: 2, red: 3 }
    for (const s of samples) {
      if (!s.ts) continue
      const t = new Date(s.ts).getTime()
      const idx = Math.min(N - 1, Math.max(0, Math.floor((t - start) / size)))
      const b = out[idx]
      b.count += 1
      if (rank[s.status] > rank[b.worst]) b.worst = s.status
    }
    return out
  }, [samples, minutes])

  const pickedIndex = useMemo(() => {
    if (!pickedTs) return null
    const t = new Date(pickedTs).getTime()
    const idx = buckets.findIndex((b, i) => {
      const next = buckets[i + 1]?.ts ?? Date.now()
      return t >= b.ts && t < next
    })
    return idx >= 0 ? idx : null
  }, [pickedTs, buckets])

  return (
    <div
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: 12,
        marginBottom: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ color: 'var(--fg-dim)', fontSize: 12, marginRight: 'auto' }}>
          Timeline {service ? `· ${service}` : '· all services'}
          {loading && ' · loading…'}
          {error && ` · ${error}`}
        </span>
        {WINDOWS.map((w) => (
          <button
            key={w.label}
            onClick={() => { setMinutes(w.minutes); onPick(null) }}
            style={{
              padding: '3px 10px',
              fontSize: 12,
              background: minutes === w.minutes ? 'var(--bg-panel-hover)' : 'transparent',
              borderColor: minutes === w.minutes ? 'var(--accent)' : 'var(--border)',
            }}
          >
            {w.label}
          </button>
        ))}
        {pickedTs && (
          <button onClick={() => onPick(null)} style={{ fontSize: 12, padding: '3px 10px' }}>
            Clear
          </button>
        )}
      </div>
      <div
        style={{
          display: 'flex',
          gap: 1,
          height: 32,
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const frac = (e.clientX - rect.left) / rect.width
          const idx = Math.min(buckets.length - 1, Math.max(0, Math.floor(frac * buckets.length)))
          onPick(new Date(buckets[idx].ts).toISOString())
        }}
      >
        {buckets.map((b, i) => (
          <div
            key={i}
            title={new Date(b.ts).toLocaleString() + (b.count ? ` — ${b.count} samples` : '')}
            style={{
              flex: 1,
              background: b.count === 0 ? 'var(--border)' : statusColor[b.worst],
              opacity: b.count === 0 ? 0.3 : 0.85,
              outline: pickedIndex === i ? '2px solid var(--accent)' : 'none',
              outlineOffset: -1,
            }}
          />
        ))}
      </div>
      {pickedTs && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--fg-dim)' }}>
          Scrubbed to {new Date(pickedTs).toLocaleString()}. All tabs are showing the state at that moment.
        </div>
      )}
    </div>
  )
}
