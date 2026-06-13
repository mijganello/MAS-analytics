// Mirror of backend Pydantic schemas

export type BlockStatus = 'complete' | 'partial' | 'error'

export interface ReportBlockBase {
  block_id: string
  block_type: string
  title: string
  order: number
  status: BlockStatus
  warnings: string[]
  source_task_ids: string[]
  created_by_dept: string
  created_at: string
}

export interface TextBlock extends ReportBlockBase {
  block_type: 'text'
  content: string
  style: 'body' | 'heading' | 'callout' | 'quote'
  language: string
}

export interface KPICard extends ReportBlockBase {
  block_type: 'kpi_card'
  metric_name: string
  value: number
  unit: string
  delta?: number
  delta_pct?: number
  trend?: 'up' | 'down' | 'stable'
  is_positive_trend?: boolean
  benchmark?: number
  verification_status: 'verified' | 'unverified'
  source_reference: string
}

export interface TableColumn {
  key: string
  label: string
  dtype: 'number' | 'string' | 'date' | 'percent' | 'currency'
  unit?: string
  sortable: boolean
  highlight_rule?: Record<string, unknown>
}

export interface TableBlock extends ReportBlockBase {
  block_type: 'table'
  columns: TableColumn[]
  rows: Record<string, unknown>[]
  totals_row?: Record<string, unknown>
  pagination: boolean
  exportable: boolean
  source_file_id: string
  source_location: string
}

export interface ChartBlock extends ReportBlockBase {
  block_type: 'chart'
  chart_type: string
  vega_lite_spec: Record<string, unknown>
  caption?: string
  data_source_description: string
  interactive: boolean
}

export interface InsightBlock extends ReportBlockBase {
  block_type: 'insight'
  insight_type: 'finding' | 'anomaly' | 'recommendation' | 'risk' | 'opportunity'
  severity: 'info' | 'warning' | 'critical'
  headline: string
  explanation: string
  supporting_data: string[]
  confidence: number
}

export interface ComparisonItem {
  label: string
  metrics: Record<string, number | string>
}

export interface ComparisonBlock extends ReportBlockBase {
  block_type: 'comparison'
  items: ComparisonItem[]
  dimensions: string[]
  winner?: string
  analysis: string
}

export interface TimePoint {
  period: string
  value: number
}

export interface ForecastPoint {
  period: string
  value: number
  lower_bound: number
  upper_bound: number
}

export interface ForecastBlock extends ReportBlockBase {
  block_type: 'forecast'
  metric_name: string
  historical: TimePoint[]
  forecast: ForecastPoint[]
  method: string
  confidence_interval: number
  model_accuracy: Record<string, number>
}

export interface RiskItem {
  name: string
  probability: 'low' | 'medium' | 'high'
  impact: 'low' | 'medium' | 'high'
  description: string
  mitigation?: string
}

export interface RiskMatrixBlock extends ReportBlockBase {
  block_type: 'risk_matrix'
  risks: RiskItem[]
  overall_risk_level: 'low' | 'medium' | 'high' | 'critical'
}

export interface ExecutiveSummaryBlock extends ReportBlockBase {
  block_type: 'executive_summary'
  key_findings: string[]
  recommendations: string[]
  overall_conclusion: string
  report_quality_score: number
}

export type ReportBlock =
  | TextBlock
  | KPICard
  | TableBlock
  | ChartBlock
  | InsightBlock
  | ComparisonBlock
  | ForecastBlock
  | RiskMatrixBlock
  | ExecutiveSummaryBlock

export interface TOCEntry {
  block_id: string
  title: string
  block_type: string
  order: number
}

export interface ReportMetadata {
  total_tokens_used: number
  processing_time_seconds: number
  departments_involved: string[]
  files_analyzed: string[]
  llm_provider: string
  model_name: string
  quality_score: number
  partial_blocks_count: number
}

export interface Report {
  report_id: string
  title: string
  created_at: string
  query: string
  blocks: ReportBlock[]
  toc: TOCEntry[]
  metadata: ReportMetadata
}

export interface SSEEvent {
  type: 'block_approved' | 'task_status' | 'session_done' | 'error'
  [key: string]: unknown
}

export interface TaskStatusEvent {
  type: 'task_status'
  task_id: string
  department: string
  status: string
  retries?: number
  tokens_used?: number
}

export interface UploadedFile {
  file_id: string
  filename: string
  file_type: string
  size_bytes: number
  status: string
}
