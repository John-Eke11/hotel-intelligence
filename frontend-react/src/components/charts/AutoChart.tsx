import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { CHART_COLORS, TOOLTIP_STYLE, AXIS_STYLE, GRID_STYLE } from './theme'
import { formatCompact } from '../../utils/format'

interface AutoChartProps {
  columns: string[]
  rows: unknown[][]
}

export default function AutoChart({ columns, rows }: AutoChartProps) {
  if (!rows.length || columns.length < 2) return null

  const data = rows.map(row => Object.fromEntries(columns.map((c, i) => [c, row[i]])))

  // Detect date and numeric columns
  const dateCol = columns.find(c => {
    const sample = String(data[0][c])
    return /^\d{4}-\d{2}/.test(sample)
  })
  const numCol = columns.find(c => typeof data[0][c] === 'number')
  const catCol = columns.find(c => typeof data[0][c] === 'string' && c !== dateCol)

  if (!numCol) return null

  if (dateCol) {
    return (
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ left: 8, right: 8, top: 8, bottom: 4 }}>
          <CartesianGrid {...GRID_STYLE} />
          <XAxis dataKey={dateCol} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS_STYLE} axisLine={false} tickLine={false} tickFormatter={v => formatCompact(Number(v))} />
          <Tooltip {...TOOLTIP_STYLE} />
          <Line type="monotone" dataKey={numCol} stroke={CHART_COLORS.primary} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (catCol && new Set(data.map(d => d[catCol])).size <= 20) {
    return (
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ left: 8, right: 8, top: 8, bottom: 4 }}>
          <CartesianGrid {...GRID_STYLE} />
          <XAxis dataKey={catCol} tick={AXIS_STYLE} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS_STYLE} axisLine={false} tickLine={false} tickFormatter={v => formatCompact(Number(v))} />
          <Tooltip {...TOOLTIP_STYLE} />
          <Bar dataKey={numCol} fill={CHART_COLORS.primary} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return null
}
