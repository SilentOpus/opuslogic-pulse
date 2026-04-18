import type { Sample } from '@/api/types'
import { formatValue, unitFor } from '@/api/units'

interface Props {
  samples: Sample[]
  width?: number
  height?: number
  color?: string
  metric?: string
}

export function Sparkline({ samples, width = 120, height = 32, color = '#6ba9ff', metric }: Props) {
  if (samples.length < 2) {
    return <svg width={width} height={height} />
  }
  const values = samples.map((s) => s.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const latest = values[values.length - 1]
  const range = max - min || 1
  const step = width / (samples.length - 1)

  const d = samples
    .map((s, i) => {
      const x = i * step
      const y = height - ((s.value - min) / range) * height
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const unit = unitFor(metric)
  const minLabel = formatValue(min, unit)
  const maxLabel = formatValue(max, unit)
  const nowLabel = formatValue(latest, unit)
  const title =
    `${metric ? metric + ' — ' : ''}min ${minLabel} · max ${maxLabel} · now ${nowLabel} (last ${samples.length} ticks)`

  return (
    <span
      title={title}
      style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'stretch', gap: 2 }}
    >
      <svg width={width} height={height} style={{ display: 'block' }}>
        <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
      </svg>
      <span
        style={{
          fontSize: 10,
          color: 'var(--fg-dim)',
          display: 'flex',
          justifyContent: 'space-between',
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1,
        }}
      >
        <span>{minLabel}</span>
        <span>{maxLabel}</span>
      </span>
    </span>
  )
}
