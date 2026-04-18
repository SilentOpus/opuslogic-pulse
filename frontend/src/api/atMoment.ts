import type { Sample } from './types'
import type { Streamed } from './usePulseStream'

/**
 * Reconstruct the "latest-as-of" sample for each timeseries from in-memory
 * history. When pickedTs is null we just return stream.latest (live).
 *
 * History only holds what's arrived via WebSocket this session — which is fine
 * for the last ~2h. For older scrub targets, tabs should fetch from /api/range
 * directly. We surface that in the UI with a "limited history" hint.
 */
export function viewAt(stream: Streamed, pickedTs: string | null): Map<string, Sample> {
  if (!pickedTs) return stream.latest

  const target = new Date(pickedTs).getTime()
  const out = new Map<string, Sample>()
  for (const [key, arr] of stream.history.entries()) {
    // Walk backwards — arr is chronological, find last sample at or before target.
    let pick: Sample | null = null
    for (let i = arr.length - 1; i >= 0; i--) {
      const ts = arr[i].ts ? new Date(arr[i].ts as string).getTime() : Date.now()
      if (ts <= target) { pick = arr[i]; break }
    }
    if (pick) out.set(key, pick)
  }
  return out
}
