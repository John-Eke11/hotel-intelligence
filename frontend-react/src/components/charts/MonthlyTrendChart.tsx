import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { MonthlyTrend } from '../../types/api'
import { TOOLTIP_STYLE, AXIS_STYLE, GRID_STYLE } from './theme'
import { formatCompact } from '../../utils/format'
import { format } from 'date-fns'

function SkeletonChart() {
  return <div className="w-full h-72 rounded animate-pulse" style={{ background: 'var(--color-bg-surface)' }} />
}

export default function MonthlyTrendChart({ data, loading }: { data: MonthlyTrend[] | null; loading: boolean }) {
  if (loading) return <SkeletonChart />
  if (!data?.length) return <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>Data unavailable.</p>

  const processed = data.map(d => ({
    ...d,
    month_label: format(new Date(d.month), 'MMM yy'),
    above_actual: Math.max(d.actual_revenue, d.target_revenue),
    below_actual: Math.min(d.actual_revenue, d.target_revenue),
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={processed} margin={{ left: 8, right: 8, top: 16, bottom: 4 }}>
        <CartesianGrid {...GRID_STYLE} />
        <XAxis dataKey="month_label" tick={AXIS_STYLE} axisLine={false} tickLine={false} />
        <YAxis tick={AXIS_STYLE} axisLine={false} tickLine={false} tickFormatter={v => `€${formatCompact(v)}`} />
        <Tooltip
          {...TOOLTIP_STYLE}
          formatter={(v, name) => {
            if (name === 'actual_revenue') return [`€${formatCompact(Number(v))}`, 'Actual']
            if (name === 'target_revenue') return [`€${formatCompact(Number(v))}`, 'Budget']
            return [null, null]
          }}
        />
        <Legend
          formatter={value => {
            if (value === 'actual_revenue') return <span style={{ color: '#B8C4D0', fontSize: 12 }}>Actual</span>
            if (value === 'target_revenue') return <span style={{ color: '#B8C4D0', fontSize: 12 }}>Budget</span>
            return null
          }}
        />
        {/* Green fill: budget baseline to max(actual, budget) */}
        <Area type="monotone" dataKey="target_revenue" stroke="none" fill="none" legendType="none" tooltipType="none" />
        <Area type="monotone" dataKey="above_actual"   stroke="none" fill="rgba(39,174,96,0.18)" legendType="none" tooltipType="none" />
        {/* Red fill: min(actual, budget) baseline to budget */}
        <Area type="monotone" dataKey="below_actual"   stroke="none" fill="none" legendType="none" tooltipType="none" />
        <Area type="monotone" dataKey="target_revenue" stroke="none" fill="rgba(231,76,60,0.18)" legendType="none" tooltipType="none" />
        {/* Lines */}
        <Line type="monotone" dataKey="actual_revenue" name="actual_revenue" stroke="#1E6091" strokeWidth={2.5} dot={{ r: 4, fill: '#1E6091' }} activeDot={{ r: 6 }} />
        <Line type="monotone" dataKey="target_revenue" name="target_revenue" stroke="#E8A020" strokeWidth={2}   dot={{ r: 4, fill: '#E8A020' }} strokeDasharray="5 4" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
