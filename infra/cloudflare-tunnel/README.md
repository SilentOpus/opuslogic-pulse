# Pulse — Cloudflare Tunnel

Pulse is reached externally at `pulse.opuslogic.eu` via Cloudflare Tunnel. Two
deployment options:

## Option A (recommended) — fold into the existing OpusLogic tunnel

The main platform already runs a tunnel from
`automation-platform/infra/cloudflare-tunnel/config.yml`. Add one ingress entry:

```yaml
ingress:
  # ...existing entries...
  - hostname: pulse.opuslogic.eu
    service: http://localhost:7600
```

Then register the DNS route once:

```bash
cloudflared tunnel route dns opuslogic-dev pulse.opuslogic.eu
```

No second tunnel process required.

## Option B — standalone Pulse tunnel

Use the `config.yml` in this directory. Run on the VPS with:

```bash
cloudflared tunnel create opuslogic-pulse
cloudflared tunnel route dns opuslogic-pulse pulse.opuslogic.eu
cloudflared tunnel --config infra/cloudflare-tunnel/config.yml run
```

Useful if you want the Pulse tunnel to survive restarts of the main platform
tunnel (true "external witness" posture).
