import { NavLink } from 'react-router-dom'
import { LayoutDashboard, MessageSquare } from 'lucide-react'
import { useEffect } from 'react'
import { api } from '../../api/client'
import { useAppContext } from '../../context/AppContext'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { to: '/chat',      label: 'Chat',      Icon: MessageSquare  },
]

export default function Sidebar() {
  const { backendStatus, setBackendStatus } = useAppContext()

  useEffect(() => {
    const check = () => api.health().then(r => setBackendStatus(r ? 'connected' : 'offline'))
    check()
    const id = setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [setBackendStatus])

  const statusColor = backendStatus === 'connected' ? '#27AE60' : backendStatus === 'offline' ? '#E74C3C' : '#E8A020'
  const statusLabel = backendStatus === 'connected' ? 'Connected' : backendStatus === 'offline' ? 'Offline' : 'Checking…'

  return (
    <aside
      className="flex flex-col h-screen"
      style={{ width: 220, minWidth: 220, background: 'var(--color-bg-base)', borderRight: '1px solid var(--color-border)', position: 'fixed', top: 0, left: 0 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <div
          className="flex items-center justify-center font-display font-bold text-bg-base"
          style={{ width: 28, height: 28, background: 'var(--color-accent)', borderRadius: 6, fontSize: 16, flexShrink: 0 }}
        >
          H
        </div>
        <div>
          <p className="font-display font-bold text-text-primary" style={{ fontSize: 16, lineHeight: 1.2 }}>HERMES</p>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.2 }}>Revenue Intelligence</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 px-3 py-4 flex-1">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className="flex items-center gap-3 px-3 py-2 rounded-md transition-colors duration-150"
            style={({ isActive }) => ({
              background: isActive ? 'var(--color-bg-surface)' : 'transparent',
              color: isActive ? 'var(--color-accent)' : 'var(--color-text-secondary)',
              borderLeft: isActive ? '3px solid var(--color-accent)' : '3px solid transparent',
              fontSize: 'var(--text-sm)',
              fontWeight: isActive ? 600 : 400,
              textDecoration: 'none',
            })}
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Status */}
      <div className="px-5 py-4" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }} />
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
            {statusLabel}
          </span>
        </div>
      </div>
    </aside>
  )
}
