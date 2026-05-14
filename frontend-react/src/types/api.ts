export interface KPIResponse {
  occupancy: number; occupancy_delta: number | null;
  adr: number; adr_delta: number | null;
  revpar: number; revpar_delta: number | null;
  trevpar: number; trevpar_delta: number | null;
}
export interface ChannelRevenue { channel: string; total_revenue: number }
export interface SegmentRevenue { segment: string; total_revenue: number }
export interface MonthlyTrend { month: string; actual_revenue: number; target_revenue: number }
export interface ApiEvent {
  event_name: string; event_type: string;
  event_start_date: string; event_end_date: string;
  historical_rate_uplift: number; is_recurring: boolean;
}
export interface ChatResponse {
  summary: string;
  sql: string | null;
  data: { columns: string[]; rows: unknown[][] } | null;
}
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string | { summary: string; sql: string | null; data: { columns: string[]; rows: unknown[][] } | null };
}
