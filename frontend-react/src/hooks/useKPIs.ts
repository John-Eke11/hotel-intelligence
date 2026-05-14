import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { KPIResponse } from '../types/api'

export function useKPIs(from: string, to: string) {
  const [data, setData]       = useState<KPIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(false)

  useEffect(() => {
    setLoading(true); setError(false)
    api.getKPIs(from, to).then(res => {
      setData(res)
      setError(res === null)
      setLoading(false)
    })
  }, [from, to])

  return { data, loading, error }
}
