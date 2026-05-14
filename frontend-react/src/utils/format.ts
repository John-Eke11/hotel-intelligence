export const formatCurrency = (v: number) =>
  new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 }).format(v)

export const formatPercent = (v: number) => `${(v * 100).toFixed(1)}%`

export const formatDelta = (v: number | null, format: 'currency' | 'percent') => {
  if (v === null) return null
  const abs = format === 'currency' ? formatCurrency(Math.abs(v)) : formatPercent(Math.abs(v))
  return { label: abs, positive: v >= 0 }
}

export const formatCompact = (v: number) =>
  new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(v)

export const formatDate = (d: Date) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
