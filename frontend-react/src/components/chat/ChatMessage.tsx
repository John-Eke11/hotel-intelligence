import { type ChatMessage as ChatMessageType } from '../../types/api'
import SQLExpander from './SQLExpander'
import AutoChart from '../charts/AutoChart'

export default function ChatMessage({ message }: { message: ChatMessageType; isLoading?: boolean }) {
  const isUser = message.role === 'user'
  const content = message.content

  if (isUser) {
    return (
      <div className="flex justify-end mb-4" style={{ animation: 'fadeInUp 150ms ease' }}>
        <div
          className="px-4 py-3 rounded-card"
          style={{ background: 'var(--color-accent)', color: '#0D1B2A', maxWidth: '80%', fontSize: 'var(--text-base)', fontWeight: 500 }}
        >
          {typeof content === 'string' ? content : ''}
        </div>
      </div>
    )
  }

  const assistantContent = typeof content === 'string' ? { summary: content, sql: null, data: null } : content

  return (
    <div className="flex justify-start mb-4" style={{ animation: 'fadeInUp 150ms ease' }}>
      <div
        className="rounded-card px-4 py-3"
        style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', maxWidth: '85%' }}
      >
        <p style={{ fontSize: 'var(--text-base)', color: 'var(--color-text-primary)', lineHeight: 1.6 }}>
          {assistantContent.summary}
        </p>
        {assistantContent.sql && <SQLExpander sql={assistantContent.sql} />}
        {assistantContent.data && assistantContent.data.rows.length > 0 && (
          <div className="mt-4">
            <div className="overflow-x-auto rounded-md" style={{ border: '1px solid var(--color-border)' }}>
              <table className="w-full" style={{ borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
                <thead>
                  <tr style={{ background: 'var(--color-bg-surface)' }}>
                    {assistantContent.data.columns.map(col => (
                      <th key={col} className="text-left px-4 py-2" style={{ color: 'var(--color-text-secondary)', fontWeight: 600, borderBottom: '1px solid var(--color-border)' }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {assistantContent.data.rows.slice(0, 50).map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      {(row as unknown[]).map((cell, j) => (
                        <td key={j} className="px-4 py-2" style={{ color: 'var(--color-text-primary)' }}>
                          {String(cell ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4">
              <AutoChart columns={assistantContent.data.columns} rows={assistantContent.data.rows} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
