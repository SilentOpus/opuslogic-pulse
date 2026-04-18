import { useMemo } from 'react'
import { StatusDot } from '@/components/StatusDot'
import { Sparkline } from '@/components/Sparkline'
import type { Sample } from '@/api/types'
import type { Streamed } from '@/api/usePulseStream'
import { keyOf } from '@/api/usePulseStream'
import { viewAt } from '@/api/atMoment'

interface Props {
  service: string
  stream: Streamed
  pickedTs: string | null
  groupBy?: keyof Sample['labels'] | 'metric'
}

export function ServiceTab({ service, stream, pickedTs, groupBy = 'metric' }: Props) {
  const samples = useMemo(
    () => [...viewAt(stream, pickedTs).values()].filter((s) => s.service === service),
    [stream.latest, stream.lastTick, service, pickedTs],
  )

  if (samples.length === 0) {
    return <div style={{ color: 'var(--fg-dim)', padding: 32 }}>No samples yet for {service}.</div>
  }

  // For the Backend tab we want per-endpoint rows; labels.route groups nicely.
  const rows = samples
    .slice()
    .sort((a, b) => {
      const ka = (a.labels[groupBy] as string) || a.metric
      const kb = (b.labels[groupBy] as string) || b.metric
      return ka.localeCompare(kb) || a.metric.localeCompare(b.metric)
    })

  return (
    <div
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        overflow: 'hidden',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: 56 }} />
          <col style={{ width: 160 }} />
          <col />
          <col style={{ width: 140 }} />
          <col style={{ width: 100 }} />
        </colgroup>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--fg-dim)', fontSize: 12 }}>
            <th style={{ padding: '10px 16px' }}>Status</th>
            <th style={{ padding: '10px 16px' }}>Metric</th>
            <th style={{ padding: '10px 16px' }}>Labels</th>
            <th style={{ padding: '10px 16px' }}>Trend</th>
            <th style={{ padding: '10px 16px', textAlign: 'right' }}>Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const k = keyOf(s)
            const hist = stream.history.get(k) ?? []
            const labels = Object.entries(s.labels).map(([k, v]) => `${k}=${v}`).join(' ') || '—'
            return (
              <tr key={k} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '10px 16px' }}>
                  <StatusDot status={s.status} />
                </td>
                <td
                  style={{
                    padding: '10px 16px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={s.metric}
                >
                  {s.metric}
                </td>
                <td
                  style={{
                    padding: '10px 16px',
                    color: 'var(--fg-dim)',
                    fontSize: 12,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={labels}
                >
                  {labels}
                </td>
                <td style={{ padding: '10px 16px' }}>
                  <Sparkline samples={hist} />
                </td>
                <td
                  style={{
                    padding: '10px 16px',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {s.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
