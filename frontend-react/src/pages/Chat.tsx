import { useRef, useEffect } from 'react'
import { useChat } from '../hooks/useChat'
import ChatMessage from '../components/chat/ChatMessage'
import ChatInput from '../components/chat/ChatInput'
import SuggestedQuestions from '../components/chat/SuggestedQuestions'
import Button from '../components/ui/Button'

export default function Chat() {
  const { chatHistory, sendMessage, clearHistory, loading } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory, loading])

  return (
    <div className="flex gap-6 h-full" style={{ minHeight: 'calc(100vh - 128px)' }}>
      {/* Left panel */}
      <div
        className="flex-shrink-0 flex flex-col gap-4 py-2"
        style={{ width: 260 }}
      >
        {chatHistory.length > 0 && (
          <Button variant="ghost" onClick={clearHistory} className="w-full text-left" style={{ fontSize: 'var(--text-sm)' }}>
            Clear history
          </Button>
        )}
        {chatHistory.length === 0 && <SuggestedQuestions onSelect={sendMessage} />}
      </div>

      {/* Chat thread */}
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex-1 overflow-y-auto pb-4" style={{ minHeight: 0 }}>
          {chatHistory.length === 0 && (
            <div className="flex items-center justify-center h-48">
              <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-base)' }}>
                Ask a question to get started.
              </p>
            </div>
          )}
          {chatHistory.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="flex items-center gap-2 px-4 py-3 rounded-card" style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)' }}>
                <div className="flex gap-1">
                  {[0,1,2].map(i => (
                    <div key={i} className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-accent)', animationDelay: `${i * 100}ms` }} />
                  ))}
                </div>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>Thinking…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <ChatInput onSend={sendMessage} loading={loading} />
      </div>
    </div>
  )
}
