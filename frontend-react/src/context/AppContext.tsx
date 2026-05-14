import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { subDays } from 'date-fns'
import { formatDate } from '../utils/format'
import type { ChatMessage } from '../types/api'

interface DateRange { from: string; to: string }

interface AppContextValue {
  dateRange: DateRange
  setDateRange: (r: DateRange) => void
  chatHistory: ChatMessage[]
  addMessage: (m: ChatMessage) => void
  clearHistory: () => void
  backendStatus: 'connected' | 'offline' | 'checking'
  setBackendStatus: (s: 'connected' | 'offline' | 'checking') => void
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const today = new Date()
  const [dateRange, setDateRange] = useState<DateRange>({
    from: formatDate(subDays(today, 30)),
    to:   formatDate(today),
  })
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [backendStatus, setBackendStatus] = useState<'connected' | 'offline' | 'checking'>('checking')

  const addMessage = useCallback((m: ChatMessage) => setChatHistory(h => [...h, m]), [])
  const clearHistory = useCallback(() => setChatHistory([]), [])

  return (
    <AppContext.Provider value={{ dateRange, setDateRange, chatHistory, addMessage, clearHistory, backendStatus, setBackendStatus }}>
      {children}
    </AppContext.Provider>
  )
}

export function useAppContext() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useAppContext must be used inside AppProvider')
  return ctx
}
