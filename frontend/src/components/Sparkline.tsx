import type { Sample } from '@/api/types'

interface Props {
  samples: Sample[]
  width?: number
  height?: number
  color?: string
}

export function Sparkline({ samples, width = 120, height = 32, color = '#6ba9ff' }: Props) {
  if (samples.length < 2) {
    return <svg width={width} height={height} />
  }
  const values = samples.map((s) => s.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const step = width / (samples.length - 1)

  const d = samples
    .map((s, i) => {
      const x = i * step
      const y = height - ((s.value - min) / range) * height
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}
