import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { KPIResponse } from '../types/api'

export function useKPIs(from: string, to: string) {
  const [data, setData]       = useState<KPIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(false)
    api.getKPIs(from, to, controller.signal).then(res => {
      if (!controller.signal.aborted) {
        setData(res)
        setError(res === null)
        setLoading(false)
      }
    })
    return () => controller.abort()
  }, [from, to])

  return { data, loading, error }
}
