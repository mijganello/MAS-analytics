const BASE = import.meta.env.VITE_API_BASE_URL || ''

export const api = {
  async uploadFiles(files: File[]): Promise<{ file_id: string; filename: string; file_type: string; size_bytes: number; status: string }[]> {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    const res = await fetch(`${BASE}/api/files/upload`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async createSession(query: string, fileIds: string[], provider?: string): Promise<{ session_id: string; status: string }> {
    const res = await fetch(`${BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, file_ids: fileIds, llm_provider: provider }),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async getSession(sessionId: string) {
    const res = await fetch(`${BASE}/api/sessions/${sessionId}`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async getReport(sessionId: string) {
    const res = await fetch(`${BASE}/api/reports/${sessionId}`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  streamReport(sessionId: string): EventSource {
    return new EventSource(`${BASE}/api/reports/${sessionId}/stream`)
  },

  async getReportLog(sessionId: string): Promise<ReportLog> {
    const res = await fetch(`${BASE}/api/reports/${sessionId}/log`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async listReports(): Promise<ReportListItem[]> {
    const res = await fetch(`${BASE}/api/reports`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async health() {
    const res = await fetch(`${BASE}/api/health`)
    return res.json()
  },
}

export interface LogEvent {
  ts: string
  type: string
  agent: string
  message: string
  task_id?: string | null
  department?: string | null
  details?: Record<string, unknown>
}

export interface ReportLog {
  session_id: string
  query: string
  status: string
  created_at: string
  completed_at: string | null
  total_tokens: number
  events: LogEvent[]
  blackboard_snapshot: {
    session: Record<string, unknown>
    task_graph: Record<string, unknown>
  }
}

export interface ReportListItem {
  report_id: string
  title: string
  query: string
  status: string
  llm_provider: string
  created_at: string
  completed_at: string | null
  total_tokens: number
}
