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
  const title = metric
    ? `${metric} — min ${formatValue(min, unit)} · max ${formatValue(max, unit)} · now ${formatValue(latest, unit)} (last ${samples.length} ticks)`
    : `min ${min.toFixed(2)} · max ${max.toFixed(2)} · now ${latest.toFixed(2)} (last ${samples.length} ticks)`

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <title>{title}</title>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}
