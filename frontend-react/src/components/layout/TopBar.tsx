import { useLocation } from 'react-router-dom'
import DateRangePicker from '../ui/DateRangePicker'
import Button from '../ui/Button'
import { useAppContext } from '../../context/AppContext'

const TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/chat':      'Revenue Chat',
}

export default function TopBar() {
  const { pathname } = useLocation()
  const { chatHistory, clearHistory } = useAppContext()
  const title = TITLES[pathname] ?? 'HERMES'

  return (
    <header
      className="flex items-center justify-between px-8 py-4"
      style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-base)', minHeight: 64 }}
    >
      <h1 className="font-display font-bold" style={{ fontSize: 'var(--text-xl)', color: 'var(--color-text-primary)' }}>
        {title}
      </h1>
      <div className="flex items-center">
        {pathname === '/dashboard' && <DateRangePicker />}
        {pathname === '/chat' && chatHistory.length > 0 && (
          <Button variant="ghost" onClick={clearHistory} style={{ fontSize: 'var(--text-sm)' }}>
            Clear history
          </Button>
        )}
      </div>
    </header>
  )
}
