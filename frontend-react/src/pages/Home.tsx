import { useAppContext } from '../context/AppContext'
import Card from '../components/ui/Card'

export default function Home() {
  const { backendStatus } = useAppContext()
  const statusMap = {
    connected: { color: '#27AE60', text: 'Backend connected — ready.' },
    offline:   { color: '#E74C3C', text: 'Backend offline — start FastAPI at http://localhost:8000.' },
    checking:  { color: '#E8A020', text: 'Checking backend…' },
  }
  const { color, text } = statusMap[backendStatus]

  return (
    <div className="max-w-4xl mx-auto">
      <h2
        className="font-display font-bold mb-3"
        style={{ fontSize: 'var(--text-3xl)', color: 'var(--color-text-primary)', letterSpacing: 'var(--tracking-tight)' }}
      >
        ATLAS
      </h2>
      <p className="mb-8" style={{ fontSize: 'var(--text-lg)', color: 'var(--color-text-secondary)' }}>
        AI-powered revenue intelligence for independent hotels.
      </p>

      {/* Status card */}
      <Card className="mb-8">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
          <span style={{ fontSize: 'var(--text-base)', color: 'var(--color-text-primary)' }}>{text}</span>
        </div>
      </Card>

      {/* Feature cards */}
      <div className="grid grid-cols-2 gap-6 mb-12">
        <Card title="Dashboard">
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-base)', lineHeight: 1.6 }}>
            Live KPI metrics, revenue breakdowns by channel and segment, actual vs budget variance, and an events calendar for the selected period.
          </p>
        </Card>
        <Card title="Chat">
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-base)', lineHeight: 1.6 }}>
            Ask revenue questions in plain English. The AI translates your question into SQL, runs it against the database, and returns a summary with the underlying data.
          </p>
        </Card>
      </div>

      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
        Prototype · Hotel Lisboa Central · 16 months synthetic data · Advanced ML — S2 T4
      </p>
    </div>
  )
}
