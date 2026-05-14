import { useState, useRef, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'

export default function ChatInput({ onSend, loading }: { onSend: (q: string) => void; loading: boolean }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const q = value.trim()
    if (!q || loading) return
    onSend(q)
    setValue('')
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  return (
    <div
      className="flex items-end gap-3 p-4 rounded-card"
      style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)' }}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKey}
        placeholder="Ask a revenue question…"
        rows={1}
        className="flex-1 resize-none bg-transparent outline-none"
        style={{
          color: 'var(--color-text-primary)',
          fontSize: 'var(--text-base)',
          fontFamily: 'var(--font-body)',
          maxHeight: '5.5rem',
          lineHeight: 1.5,
          border: 'none',
        }}
        disabled={loading}
      />
      <button
        onClick={submit}
        disabled={!value.trim() || loading}
        className="flex items-center justify-center rounded-md transition-colors duration-150 disabled:opacity-40"
        style={{ background: 'var(--color-accent)', width: 36, height: 36, flexShrink: 0, border: 'none', cursor: 'pointer' }}
      >
        <Send size={16} color="#0D1B2A" />
      </button>
    </div>
  )
}
