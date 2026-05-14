import type { CSSProperties } from 'react'
import { useAppContext } from '../../context/AppContext'

export default function DateRangePicker() {
  const { dateRange, setDateRange } = useAppContext()

  const inputStyle: CSSProperties = {
    background: 'var(--color-bg-surface)',
    border: '1px solid var(--color-border-strong)',
    borderRadius: '6px',
    color: 'var(--color-text-primary)',
    padding: '6px 10px',
    fontSize: 'var(--text-sm)',
    colorScheme: 'dark',
    outline: 'none',
    cursor: 'pointer',
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="date"
        value={dateRange.from}
        max={dateRange.to}
        onChange={e => setDateRange({ ...dateRange, from: e.target.value })}
        style={inputStyle}
      />
      <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>–</span>
      <input
        type="date"
        value={dateRange.to}
        min={dateRange.from}
        onChange={e => setDateRange({ ...dateRange, to: e.target.value })}
        style={inputStyle}
      />
    </div>
  )
}
