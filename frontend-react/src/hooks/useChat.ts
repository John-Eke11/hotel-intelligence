import { useState, useCallback } from 'react'
import { api } from '../api/client'
import { useAppContext } from '../context/AppContext'

export function useChat() {
  const { chatHistory, addMessage, clearHistory } = useAppContext()
  const [loading, setLoading] = useState(false)

  const sendMessage = useCallback(async (query: string) => {
    addMessage({ role: 'user', content: query })
    setLoading(true)
    const res = await api.chat(query, chatHistory)
    setLoading(false)
    if (res) {
      addMessage({ role: 'assistant', content: { summary: res.summary, sql: res.sql, data: res.data } })
    } else {
      addMessage({ role: 'assistant', content: { summary: 'Sorry — the backend is not reachable. Please start the FastAPI server and try again.', sql: null, data: null } })
    }
  }, [chatHistory, addMessage])

  return { chatHistory, sendMessage, clearHistory, loading }
}
