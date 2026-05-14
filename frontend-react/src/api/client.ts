import type { KPIResponse, ChannelRevenue, SegmentRevenue, MonthlyTrend, ApiEvent, ChatResponse, ChatMessage } from '../types/api'

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

async function get<T>(path: string, params: Record<string, string> = {}, signal?: AbortSignal): Promise<T | null> {
  try {
    const qs = new URLSearchParams(params).toString()
    const res = await fetch(`${BASE_URL}${path}${qs ? '?' + qs : ''}`, { signal })
    if (!res.ok) return null
    return res.json() as Promise<T>
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return null
    return null
  }
}

async function post<T>(path: string, body: unknown): Promise<T | null> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return res.json() as Promise<T>
  } catch { return null }
}

export const api = {
  health:              () => get<{ status: string }>('/health'),
  getKPIs:             (from: string, to: string, signal?: AbortSignal) => get<KPIResponse>('/metrics/kpis', { from_date: from, to_date: to, property_id: '1' }, signal),
  getRevenueByChannel: (from: string, to: string, signal?: AbortSignal) => get<ChannelRevenue[]>('/metrics/revenue-by-channel', { from_date: from, to_date: to, property_id: '1' }, signal),
  getRevenueBySegment: (from: string, to: string, signal?: AbortSignal) => get<SegmentRevenue[]>('/metrics/revenue-by-segment', { from_date: from, to_date: to, property_id: '1' }, signal),
  getMonthlyTrend:     (from: string, to: string, signal?: AbortSignal) => get<MonthlyTrend[]>('/metrics/monthly-trend', { from_date: from, to_date: to, property_id: '1' }, signal),
  getEvents:           (from: string, to: string, signal?: AbortSignal) => get<ApiEvent[]>('/events', { from_date: from, to_date: to }, signal),
  chat:                (query: string, messages: ChatMessage[]) =>
    post<ChatResponse>('/chat', { query, property_id: 1, messages }),
}
