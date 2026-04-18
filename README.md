# OpusLogic Pulse

External observability dashboard for the OpusLogic Automation Platform.

Fully in-house stack — no third-party observability vendors. Collector polls every
service, stores time-series in DuckDB, streams live updates over WebSocket, and
renders a tabbed React dashboard matching the OpusLogic visual language.

## Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Collector   │─────▶│   DuckDB     │◀─────│   API + WS   │
│  (FastAPI)   │      │  (timeseries)│      │  (FastAPI)   │
└──────┬───────┘      └──────────────┘      └──────┬───────┘
       │                                            │
       │ probes                                     │ WebSocket
       ▼                                            ▼
  Backend /health                             React/Vite UI
  Temporal gRPC                               (7 tabs)
  Postgres pg_stat_*
  Zitadel /healthz
  Docker socket
  /proc (host)
  Agent heartbeats
```

## Tabs

1. **Overview** — traffic-light view of every service, recent incidents
2. **Backend API** — per-endpoint latency, RPS, error rate, synthetic probes
3. **Temporal** — workflow queue depth, worker health, task latency
4. **Postgres** — connections, slow queries, replication, lock waits
5. **Zitadel** — token issuance, login success rate, API latency
6. **Agents** — enrolled agents, heartbeat gaps, version distribution
7. **Host** — CPU, memory, disk, network on the VPS itself

Each tab has a timeline scrubber for postmortems ("what went wrong when").

## Deployment

Deploys alongside OpusLogic on the same VPS with its own docker-compose stack,
reached at `pulse.opuslogic.eu` via the existing Cloudflare tunnel.

```bash
./scripts/deploy.sh
```

## Status

Scaffold — collector framework, DuckDB storage, WebSocket stream, and Overview
tab wired up with host-metrics probe as proof of the pipeline. Additional probes
and tabs land in subsequent iterations.
