import { useEffect, useState } from 'react'
import { formatDelta } from '../../utils/format'

interface KPICardProps {
  label: string
  value: string
  delta: number | null
  format: 'currency' | 'percent'
  loading?: boolean
}

function SkeletonKPI() {
  return (
    <div className="rounded-card p-6 animate-pulse" style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)' }}>
      <div className="h-3 w-20 rounded mb-4" style={{ background: 'var(--color-bg-surface)' }} />
      <div className="h-9 w-32 rounded mb-3" style={{ background: 'var(--color-bg-surface)' }} />
      <div className="h-3 w-24 rounded" style={{ background: 'var(--color-bg-surface)' }} />
    </div>
  )
}

export default function KPICard({ label, value, delta, format, loading }: KPICardProps) {
  const [displayed, setDisplayed] = useState('0')

  useEffect(() => {
    if (loading) return
    setDisplayed(value)
  }, [value, loading])

  if (loading) return <SkeletonKPI />

  const d = formatDelta(delta, format)

  return (
    <div
      className="rounded-card p-6"
      style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', boxShadow: '0 1px 4px rgba(0,0,0,0.3)' }}
    >
      <p
        className="uppercase mb-3"
        style={{ fontSize: 'var(--text-xs)', letterSpacing: 'var(--tracking-caps)', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-body)' }}
      >
        {label}
      </p>
      <p
        className="font-display mb-2"
        style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, letterSpacing: 'var(--tracking-tight)', color: 'var(--color-text-primary)', lineHeight: 1 }}
      >
        {displayed}
      </p>
      {d ? (
        <p className="text-xs font-semibold" style={{ color: d.positive ? 'var(--color-positive)' : 'var(--color-negative)' }}>
          {d.positive ? '▲' : '▼'} {d.label} vs. prev. period
        </p>
      ) : (
        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>no comparison data</p>
      )}
    </div>
  )
}
