import { useMemo } from 'react'
import { StatusDot } from '@/components/StatusDot'
import { Sparkline } from '@/components/Sparkline'
import type { Sample, Status } from '@/api/types'
import type { Streamed } from '@/api/usePulseStream'
import { keyOf } from '@/api/usePulseStream'
import { viewAt } from '@/api/atMoment'
import { formatValue, unitFor } from '@/api/units'

const SERVICE_ORDER = ['host', 'backend', 'temporal', 'postgres', 'zitadel', 'docker', 'agents']

const worstStatus = (ss: Status[]): Status => {
  if (ss.includes('red')) return 'red'
  if (ss.includes('amber')) return 'amber'
  if (ss.includes('green')) return 'green'
  return 'unknown'
}

export function OverviewTab({ stream, pickedTs }: { stream: Streamed; pickedTs: string | null }) {
  const byService = useMemo(() => {
    const source = viewAt(stream, pickedTs)
    const m = new Map<string, Sample[]>()
    for (const s of source.values()) {
      const arr = m.get(s.service) ?? []
      arr.push(s)
      m.set(s.service, arr)
    }
    return m
  }, [stream.latest, stream.lastTick, pickedTs])

  const services = SERVICE_ORDER.filter((s) => byService.has(s)).concat(
    [...byService.keys()].filter((s) => !SERVICE_ORDER.includes(s)),
  )

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16 }}>
      {services.map((svc) => {
        const samples = byService.get(svc) ?? []
        const status = worstStatus(samples.map((s) => s.status))
        const shown = samples
          .slice()
          .sort((a, b) => a.metric.localeCompare(b.metric))
          .slice(0, 6)
        return (
          <div
            key={svc}
            style={{
              background: 'var(--bg-panel)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: 16,
              minWidth: 0,
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12, gap: 8, minWidth: 0 }}>
              <StatusDot status={status} />
              <h3 style={{ margin: 0, fontSize: 16, textTransform: 'capitalize' }}>{svc}</h3>
              <span style={{ marginLeft: 'auto', color: 'var(--fg-dim)', fontSize: 12, whiteSpace: 'nowrap' }}>
                {samples.length} metric{samples.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {shown.map((s) => {
                const k = keyOf(s)
                const hist = stream.history.get(k) ?? []
                const labelText = Object.entries(s.labels)
                  .filter(([k]) => !['code', 'path'].includes(k))
                  .map(([k, v]) => `${k}=${v}`)
                  .join(' ')
                return (
                  <div
                    key={k}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(0, 1fr) 80px 64px',
                      alignItems: 'center',
                      gap: 10,
                      minWidth: 0,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.metric}
                      </div>
                      {labelText && (
                        <div
                          title={labelText}
                          style={{
                            fontSize: 11,
                            color: 'var(--fg-dim)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {labelText}
                        </div>
                      )}
                    </div>
                    <Sparkline samples={hist} width={80} metric={s.metric} />
                    <span
                      title={`${s.metric}: ${formatValue(s.value, unitFor(s.metric))}`}
                      style={{
                        fontVariantNumeric: 'tabular-nums',
                        textAlign: 'right',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formatValue(s.value, unitFor(s.metric))}
                    </span>
                  </div>
                )
              })}
              {samples.length > shown.length && (
                <div style={{ color: 'var(--fg-dim)', fontSize: 11, textAlign: 'right' }}>
                  +{samples.length - shown.length} more
                </div>
              )}
            </div>
          </div>
        )
      })}
      {services.length === 0 && (
        <div style={{ color: 'var(--fg-dim)', padding: 32 }}>Waiting for first sample tick…</div>
      )}
    </div>
  )
}
