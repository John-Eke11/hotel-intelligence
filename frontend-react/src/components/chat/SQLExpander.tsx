import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

export default function SQLExpander({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3 rounded-md overflow-hidden" style={{ border: '1px solid var(--color-border)' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between w-full px-4 py-2 transition-colors duration-150"
        style={{ background: 'var(--color-bg-surface)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', cursor: 'pointer', border: 'none' }}
      >
        <span>View generated SQL</span>
        <ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }} />
      </button>
      {open && (
        <pre
          className="p-4 overflow-x-auto"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: '#B8C4D0', background: '#0D1B2A', margin: 0 }}
        >
          <code>{sql}</code>
        </pre>
      )}
    </div>
  )
}
