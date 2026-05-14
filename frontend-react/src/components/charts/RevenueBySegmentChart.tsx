import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { SegmentRevenue } from '../../types/api'
import { CHART_COLORS, TOOLTIP_STYLE } from './theme'
import { formatCompact } from '../../utils/format'

function SkeletonChart() {
  return <div className="w-full h-64 rounded animate-pulse" style={{ background: 'var(--color-bg-surface)' }} />
}

export default function RevenueBySegmentChart({ data, loading }: { data: SegmentRevenue[] | null; loading: boolean }) {
  if (loading) return <SkeletonChart />
  if (!data?.length) return <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>Data unavailable.</p>

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="total_revenue" nameKey="segment" innerRadius={60} outerRadius={100} paddingAngle={2}>
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS.segments[i % CHART_COLORS.segments.length]} />)}
        </Pie>
        <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [`€${formatCompact(Number(v))}`, 'Revenue']} />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => <span style={{ color: '#B8C4D0', fontSize: 12 }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
