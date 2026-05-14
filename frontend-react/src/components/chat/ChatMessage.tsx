import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { User } from 'lucide-react'
import { type ChatMessage as ChatMessageType } from '../../types/api'
import SQLExpander from './SQLExpander'
import AutoChart from '../charts/AutoChart'

export function AssistantAvatar() {
  return (
    <div
      className="flex-shrink-0 flex items-center justify-center rounded-full font-display font-bold"
      style={{
        width: 32, height: 32, flexShrink: 0,
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
        color: 'var(--color-accent)',
        fontSize: 14, lineHeight: 1,
      }}
    >
      H
    </div>
  )
}

export function UserAvatar() {
  return (
    <div
      className="flex-shrink-0 flex items-center justify-center rounded-full"
      style={{ width: 32, height: 32, flexShrink: 0, background: 'var(--color-accent)' }}
    >
      <User size={16} color="#0D1B2A" />
    </div>
  )
}

// Markdown component overrides — styled to match the dark design system
const md = {
  p:      ({ children }: { children?: React.ReactNode }) =>
            <p style={{ margin: '0 0 0.55em 0', lineHeight: 1.65, color: 'var(--color-text-primary)' }}>{children}</p>,
  ul:     ({ children }: { children?: React.ReactNode }) =>
            <ul style={{ paddingLeft: '1.3em', margin: '0.4em 0 0.55em', listStyleType: 'disc', color: 'var(--color-text-primary)' }}>{children}</ul>,
  ol:     ({ children }: { children?: React.ReactNode }) =>
            <ol style={{ paddingLeft: '1.3em', margin: '0.4em 0 0.55em', listStyleType: 'decimal', color: 'var(--color-text-primary)' }}>{children}</ol>,
  li:     ({ children }: { children?: React.ReactNode }) =>
            <li style={{ margin: '0.2em 0', lineHeight: 1.55 }}>{children}</li>,
  strong: ({ children }: { children?: React.ReactNode }) =>
            <strong style={{ fontWeight: 700, color: 'var(--color-text-primary)' }}>{children}</strong>,
  em:     ({ children }: { children?: React.ReactNode }) =>
            <em style={{ color: 'var(--color-text-secondary)' }}>{children}</em>,
  h1:     ({ children }: { children?: React.ReactNode }) =>
            <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, margin: '0.4em 0 0.3em', color: 'var(--color-text-primary)' }}>{children}</h1>,
  h2:     ({ children }: { children?: React.ReactNode }) =>
            <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, margin: '0.4em 0 0.3em', color: 'var(--color-text-primary)' }}>{children}</h2>,
  h3:     ({ children }: { children?: React.ReactNode }) =>
            <h3 style={{ fontSize: 'var(--text-md)', fontWeight: 600, margin: '0.4em 0 0.3em', color: 'var(--color-text-primary)' }}>{children}</h3>,
  // pre wraps fenced code blocks
  pre:    ({ children }: { children?: React.ReactNode }) =>
            <pre style={{ background: 'var(--color-bg-base)', padding: 12, borderRadius: 6, overflowX: 'auto', margin: '0.5em 0', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: '#B8C4D0' }}>{children}</pre>,
  // code: pill for inline, minimal for inside pre (block)
  code:   ({ children, className }: { children?: React.ReactNode; className?: string }) =>
            className
              ? <code className={className} style={{ fontFamily: 'var(--font-mono)', color: '#B8C4D0' }}>{children}</code>
              : <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85em', background: 'var(--color-bg-surface)', padding: '1px 5px', borderRadius: 4, color: 'var(--color-accent)' }}>{children}</code>,
}

export default function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === 'user'
  const content = message.content

  if (isUser) {
    return (
      <div className="flex justify-end items-start gap-3 mb-4" style={{ animation: 'fadeInUp 150ms ease' }}>
        <div
          className="px-4 py-3 rounded-card"
          style={{ background: 'var(--color-accent)', color: '#0D1B2A', maxWidth: '75%', fontSize: 'var(--text-base)', fontWeight: 500, lineHeight: 1.5 }}
        >
          {typeof content === 'string' ? content : ''}
        </div>
        <UserAvatar />
      </div>
    )
  }

  const assistantContent = typeof content === 'string'
    ? { summary: content, sql: null, data: null }
    : content

  return (
    <div className="flex justify-start items-start gap-3 mb-4" style={{ animation: 'fadeInUp 150ms ease' }}>
      <AssistantAvatar />
      <div
        className="rounded-card px-4 py-3"
        style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', maxWidth: '85%', minWidth: 0 }}
      >
        <div style={{ fontSize: 'var(--text-base)' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={md as object}>
            {assistantContent.summary}
          </ReactMarkdown>
        </div>

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
