import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  hover?: boolean
}

export default function Card({ children, className = '', title, hover = false }: CardProps) {
  return (
    <div
      className={`rounded-card border p-6 ${hover ? 'transition-shadow duration-150 hover:shadow-lg' : ''} ${className}`}
      style={{
        background: 'var(--color-bg-elevated)',
        borderColor: 'var(--color-border)',
        boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
      }}
    >
      {title && (
        <p
          className="mb-3 uppercase tracking-widest"
          style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', letterSpacing: 'var(--tracking-caps)', fontFamily: 'var(--font-body)', paddingBottom: '10px', borderBottom: '1px solid var(--color-border)' }}
        >
          {title}
        </p>
      )}
      {children}
    </div>
  )
}
