import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { ChannelRevenue, SegmentRevenue, MonthlyTrend, ApiEvent } from '../types/api'

function makeHook<T>(fetcher: (f: string, t: string, signal: AbortSignal) => Promise<T[] | null>) {
  return function useData(from: string, to: string) {
    const [data, setData]       = useState<T[] | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
      const controller = new AbortController()
      setLoading(true)
      fetcher(from, to, controller.signal).then(res => {
        if (!controller.signal.aborted) {
          setData(res)
          setLoading(false)
        }
      })
      return () => controller.abort()
    }, [from, to])

    return { data, loading }
  }
}

export const useRevenueByChannel = makeHook<ChannelRevenue>(api.getRevenueByChannel)
export const useRevenueBySegment = makeHook<SegmentRevenue>(api.getRevenueBySegment)
export const useMonthlyTrend     = makeHook<MonthlyTrend>(api.getMonthlyTrend)
export const useEvents           = makeHook<ApiEvent>(api.getEvents)
