type Variant = 'accent' | 'positive' | 'negative' | 'neutral' | 'sporting' | 'festival' | 'congress' | 'holiday'

const STYLES: Record<Variant, { bg: string; color: string }> = {
  accent:   { bg: 'rgba(232,160,32,0.15)',   color: '#E8A020' },
  positive: { bg: 'rgba(39,174,96,0.15)',    color: '#27AE60' },
  negative: { bg: 'rgba(231,76,60,0.15)',    color: '#E74C3C' },
  neutral:  { bg: 'rgba(184,196,208,0.15)',  color: '#B8C4D0' },
  sporting: { bg: 'rgba(30,96,145,0.20)',    color: '#5B9BD5' },
  festival: { bg: 'rgba(232,160,32,0.20)',   color: '#E8A020' },
  congress: { bg: 'rgba(162,59,114,0.20)',   color: '#954F72' },
  holiday:  { bg: 'rgba(39,174,96,0.20)',    color: '#27AE60' },
}

export default function Badge({ label, variant }: { label: string; variant: Variant }) {
  const { bg, color } = STYLES[variant] ?? STYLES.neutral
  return (
    <span
      style={{ background: bg, color, fontSize: 'var(--text-xs)', fontWeight: 600, padding: '2px 10px', borderRadius: '12px', display: 'inline-block' }}
    >
      {label}
    </span>
  )
}
