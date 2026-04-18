export type Unit = '%' | 'ms' | 's' | 'GB' | 'MB' | 'Mbps' | 'count' | ''

/** Infer a unit from the metric name so we can suffix numbers consistently. */
export function unitFor(metric?: string): Unit {
  if (!metric) return ''
  if (metric.endsWith('_pct')) return '%'
  if (metric.endsWith('_ms')) return 'ms'
  if (metric.endsWith('_sec') || metric.endsWith('_s')) return 's'
  if (metric.endsWith('_gb')) return 'GB'
  if (metric.endsWith('_mb')) return 'MB'
  if (metric.endsWith('_mbps')) return 'Mbps'
  if (['connections', 'slow_queries', 'locks_waiting', 'healthy', 'stale', 'total',
       'workers_reachable', 'queue_backlog'].includes(metric)) return 'count'
  return ''
}

export function formatValue(value: number, unit: Unit): string {
  const n = Number.isFinite(value) ? value : 0
  const digits = unit === '%' || unit === 'ms' || unit === 'Mbps' ? 2 : (unit === 'count' ? 0 : 2)
  const str = n.toLocaleString(undefined, { maximumFractionDigits: digits })
  return unit ? `${str} ${unit}` : str
}
