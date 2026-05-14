const QUESTIONS = [
  'How did we price against competitors during Ironman Cascais 2025?',
  'How was our channel performance last month vs same time last year?',
  'What is the average stay length for corporate guests this year?',
  'Explain the hospitality industry to me like I am 5.',
]

export default function SuggestedQuestions({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col gap-3">
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', letterSpacing: 'var(--tracking-caps)', textTransform: 'uppercase' }}>
        Suggested questions
      </p>
      {QUESTIONS.map(q => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          className="text-left px-4 py-3 rounded-md transition-colors duration-150"
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--text-sm)',
            cursor: 'pointer',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--color-accent)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-text-primary)' }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--color-border)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-text-secondary)' }}
        >
          {q}
        </button>
      ))}
    </div>
  )
}
