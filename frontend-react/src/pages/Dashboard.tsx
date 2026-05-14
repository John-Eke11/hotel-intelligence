import { useAppContext } from '../context/AppContext'
import { useKPIs } from '../hooks/useKPIs'
import { useRevenueByChannel, useRevenueBySegment, useMonthlyTrend, useEvents } from '../hooks/useRevenue'
import KPICard from '../components/ui/KPICard'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import RevenueByChannelChart from '../components/charts/RevenueByChannelChart'
import RevenueBySegmentChart from '../components/charts/RevenueBySegmentChart'
import MonthlyTrendChart from '../components/charts/MonthlyTrendChart'
import { formatCurrency, formatPercent } from '../utils/format'
import type { ApiEvent } from '../types/api'

type BadgeVariant = 'sporting' | 'festival' | 'congress' | 'holiday' | 'neutral'

function eventBadgeVariant(type: string): BadgeVariant {
  if (['sporting', 'festival', 'congress', 'holiday'].includes(type)) return type as BadgeVariant
  return 'neutral'
}

function EventsTable({ data, loading }: { data: ApiEvent[] | null; loading: boolean }) {
  if (loading) return <div className="h-40 rounded animate-pulse" style={{ background: 'var(--color-bg-surface)' }} />
  if (!data?.length) return <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>No events in this period.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full" style={{ borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
        <thead>
          <tr>
            {['Event', 'Type', 'Start', 'End', 'Rate Uplift', 'Recurring'].map(h => (
              <th key={h} className="text-left px-4 py-2" style={{ color: 'var(--color-text-secondary)', fontWeight: 600, borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-surface)' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((e, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td className="px-4 py-2" style={{ color: 'var(--color-text-primary)' }}>{e.event_name}</td>
              <td className="px-4 py-2"><Badge label={e.event_type} variant={eventBadgeVariant(e.event_type)} /></td>
              <td className="px-4 py-2" style={{ color: 'var(--color-text-secondary)' }}>{e.event_start_date}</td>
              <td className="px-4 py-2" style={{ color: 'var(--color-text-secondary)' }}>{e.event_end_date}</td>
              <td className="px-4 py-2" style={{ color: 'var(--color-positive)', fontWeight: 600 }}>+{(e.historical_rate_uplift * 100).toFixed(0)}%</td>
              <td className="px-4 py-2" style={{ color: 'var(--color-text-secondary)' }}>{e.is_recurring ? 'Yes' : 'No'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Dashboard() {
  const { dateRange } = useAppContext()
  const { from, to } = dateRange

  const { data: kpis, loading: kpiLoading }     = useKPIs(from, to)
  const { data: channels, loading: chLoading }   = useRevenueByChannel(from, to)
  const { data: segments, loading: segLoading }  = useRevenueBySegment(from, to)
  const { data: trend, loading: trendLoading }   = useMonthlyTrend(from, to)
  const { data: events, loading: eventsLoading } = useEvents(from, to)

  return (
    <div className="flex flex-col gap-6">
      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard label="Occupancy" value={kpis ? formatPercent(kpis.occupancy)   : '—'} delta={kpis?.occupancy_delta ?? null} format="percent"  loading={kpiLoading} />
        <KPICard label="ADR"       value={kpis ? formatCurrency(kpis.adr)        : '—'} delta={kpis?.adr_delta      ?? null} format="currency" loading={kpiLoading} />
        <KPICard label="RevPAR"    value={kpis ? formatCurrency(kpis.revpar)     : '—'} delta={kpis?.revpar_delta   ?? null} format="currency" loading={kpiLoading} />
        <KPICard label="TRevPAR"   value={kpis ? formatCurrency(kpis.trevpar)    : '—'} delta={kpis?.trevpar_delta  ?? null} format="currency" loading={kpiLoading} />
      </div>

      {/* Revenue Row */}
      <div className="grid grid-cols-2 gap-6">
        <Card title="Revenue by Channel" hover>
          <RevenueByChannelChart data={channels} loading={chLoading} />
        </Card>
        <Card title="Revenue by Segment" hover>
          <RevenueBySegmentChart data={segments} loading={segLoading} />
        </Card>
      </div>

      {/* Monthly Trend */}
      <Card title="Monthly Revenue vs Budget" hover>
        <MonthlyTrendChart data={trend} loading={trendLoading} />
      </Card>

      {/* Events */}
      <Card title="Events in Period">
        <p className="mb-4" style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
          External demand drivers — sporting events, congresses, festivals — that affect market rates.
        </p>
        <EventsTable data={events} loading={eventsLoading} />
      </Card>
    </div>
  )
}
