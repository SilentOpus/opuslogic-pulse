import type { Sample } from './types'
import { getAccessToken } from '@/auth/oidc'

export interface RangeResponse {
  samples: Sample[]
}

export async function fetchRange(service: string | null, minutes: number): Promise<Sample[]> {
  const q = new URLSearchParams({ minutes: String(minutes) })
  if (service) q.set('service', service)
  const token = await getAccessToken()
  const r = await fetch(`/api/range?${q.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!r.ok) throw new Error(`range ${r.status}`)
  const body: RangeResponse = await r.json()
  return body.samples.map((s) => ({ ...s, ts: s.ts || undefined }))
}
