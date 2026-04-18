export type Status = 'green' | 'amber' | 'red' | 'unknown'

export interface Sample {
  service: string
  metric: string
  value: number
  status: Status
  labels: Record<string, string>
  message: string
  ts?: string
}

export interface SamplesMessage {
  type: 'samples' | 'snapshot'
  ts?: string
  samples: Sample[]
}
