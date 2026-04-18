import { useEffect, useState } from 'react'
import {
  Activity,
  Boxes,
  Cpu,
  Database,
  KeyRound,
  LogOut,
  Network,
  Workflow,
  Users,
} from 'lucide-react'
import { usePulseStream } from './api/usePulseStream'
import { OverviewTab } from './tabs/OverviewTab'
import { ServiceTab } from './tabs/ServiceTab'
import { TimelineScrubber } from './components/TimelineScrubber'
import { getUsername, logout } from './auth/oidc'

type TabId = 'overview' | 'backend' | 'temporal' | 'postgres' | 'zitadel' | 'docker' | 'agents' | 'host'

interface TabDef {
  id: TabId
  label: string
  icon: React.ComponentType<{ size?: number }>
}

const TABS: TabDef[] = [
  { id: 'overview', label: 'Overview',  icon: Activity },
  { id: 'backend',  label: 'Backend API', icon: Network },
  { id: 'temporal', label: 'Temporal',  icon: Workflow },
  { id: 'postgres', label: 'Postgres',  icon: Database },
  { id: 'zitadel',  label: 'Zitadel',   icon: KeyRound },
  { id: 'docker',   label: 'Containers', icon: Boxes },
  { id: 'agents',   label: 'Agents',    icon: Users },
  { id: 'host',     label: 'Host',      icon: Cpu },
]

export function App() {
  const [active, setActive] = useState<TabId>('overview')
  const [pickedTs, setPickedTs] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const stream = usePulseStream()

  useEffect(() => { void getUsername().then(setUsername) }, [])

  const scrubberService = active === 'overview' ? null : active

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <aside
        style={{
          width: 220,
          background: 'var(--bg-panel)',
          borderRight: '1px solid var(--border)',
          padding: '20px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        <div style={{ padding: '0 10px 20px', fontWeight: 600, fontSize: 16 }}>
          OpusLogic <span style={{ color: 'var(--accent)' }}>Pulse</span>
        </div>
        {TABS.map((t) => {
          const Icon = t.icon
          const isActive = active === t.id
          return (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                textAlign: 'left',
                padding: '8px 12px',
                border: '1px solid transparent',
                background: isActive ? 'var(--bg-panel-hover)' : 'transparent',
                borderColor: isActive ? 'var(--border)' : 'transparent',
                borderRadius: 6,
              }}
            >
              <Icon size={16} />
              <span>{t.label}</span>
            </button>
          )
        })}
        <div style={{ marginTop: 'auto', padding: '10px', color: 'var(--fg-dim)', fontSize: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              className={`dot ${stream.connected ? 'green' : 'red'}`}
              style={{ width: 8, height: 8 }}
            />
            {stream.connected ? 'Live' : 'Reconnecting…'}
          </div>
          {stream.lastTick && (
            <div style={{ marginTop: 4 }}>last tick {new Date(stream.lastTick).toLocaleTimeString()}</div>
          )}
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {username || '—'}
            </span>
            <button
              onClick={() => void logout()}
              title="Sign out"
              style={{ padding: '3px 6px', border: '1px solid var(--border)' }}
            >
              <LogOut size={12} />
            </button>
          </div>
        </div>
      </aside>

      <main style={{ flex: 1, padding: 24, overflow: 'auto' }}>
        <h2 style={{ marginTop: 0 }}>{TABS.find((t) => t.id === active)?.label}</h2>
        <TimelineScrubber service={scrubberService} pickedTs={pickedTs} onPick={setPickedTs} />
        {active === 'overview' ? (
          <OverviewTab stream={stream} pickedTs={pickedTs} />
        ) : (
          <ServiceTab
            service={active}
            stream={stream}
            pickedTs={pickedTs}
            groupBy={active === 'backend' ? 'route' : 'metric'}
          />
        )}
      </main>
    </div>
  )
}
