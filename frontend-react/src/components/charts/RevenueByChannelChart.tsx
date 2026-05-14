import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { ChannelRevenue } from '../../types/api'
import { CHART_COLORS, TOOLTIP_STYLE, AXIS_STYLE, GRID_STYLE } from './theme'
import { formatCompact } from '../../utils/format'

function SkeletonChart() {
  return <div className="w-full h-64 rounded animate-pulse" style={{ background: 'var(--color-bg-surface)' }} />
}

export default function RevenueByChannelChart({ data, loading }: { data: ChannelRevenue[] | null; loading: boolean }) {
  if (loading) return <SkeletonChart />
  if (!data?.length) return <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>Data unavailable.</p>

  const sorted = [...data].sort((a, b) => a.total_revenue - b.total_revenue)

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={sorted} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <CartesianGrid {...GRID_STYLE} horizontal={false} />
        <XAxis type="number" tick={AXIS_STYLE} tickFormatter={v => `€${formatCompact(v)}`} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="channel" tick={AXIS_STYLE} axisLine={false} tickLine={false} width={100} />
        <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [`€${formatCompact(Number(v))}`, 'Revenue']} />
        <Bar dataKey="total_revenue" radius={[0, 4, 4, 0]}>
          {sorted.map((_, i) => <Cell key={i} fill={CHART_COLORS.channels[i % CHART_COLORS.channels.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
