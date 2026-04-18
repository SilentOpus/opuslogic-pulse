import type { Status } from '@/api/types'

export function StatusDot({ status }: { status: Status }) {
  return <span className={`dot ${status}`} aria-label={status} />
}
