import { useLocation } from 'react-router-dom'
import DateRangePicker from '../ui/DateRangePicker'

const TITLES: Record<string, string> = {
  '/':          'Home',
  '/dashboard': 'Dashboard',
  '/chat':      'Revenue Chat',
}

export default function TopBar() {
  const { pathname } = useLocation()
  const title = TITLES[pathname] ?? 'ATLAS'

  return (
    <header
      className="flex items-center justify-between px-8 py-4"
      style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-base)', minHeight: 64 }}
    >
      <h1 className="font-display font-bold" style={{ fontSize: 'var(--text-xl)', color: 'var(--color-text-primary)' }}>
        {title}
      </h1>
      {pathname === '/dashboard' && <DateRangePicker />}
    </header>
  )
}
