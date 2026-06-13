import React, { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { BlockRenderer } from '@/components/blocks/BlockRenderer'
import { BlockErrorBoundary } from '@/components/BlockErrorBoundary'
import { AgentLog } from '@/components/AgentLog'
import type { LogEvent } from '@/app/store'
import { BarChart3, ArrowLeft, Calendar, Cpu, AlertCircle, FileText, ScrollText } from 'lucide-react'
import type { ReportBlock } from '@/types/blocks'

type BlockGroup =
  | { kind: 'kpi_grid'; blocks: ReportBlock[] }
  | { kind: 'single'; block: ReportBlock }

function groupBlocks(blocks: ReportBlock[]): BlockGroup[] {
  const groups: BlockGroup[] = []
  let i = 0
  while (i < blocks.length) {
    if (blocks[i].block_type === 'kpi_card') {
      const run: ReportBlock[] = []
      while (i < blocks.length && blocks[i].block_type === 'kpi_card') {
        run.push(blocks[i++])
      }
      groups.push({ kind: 'kpi_grid', blocks: run })
    } else {
      groups.push({ kind: 'single', block: blocks[i++] })
    }
  }
  return groups
}

function gridCols(count: number): string {
  if (count === 1) return 'grid-cols-1'
  if (count === 2) return 'grid-cols-2'
  if (count === 3) return 'grid-cols-3'
  return 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4'
}

export const ReportViewer: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [activeTab, setActiveTab] = useState<'report' | 'log'>('report')

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['report', sessionId],
    queryFn: () => api.getReport(sessionId!),
    enabled: !!sessionId,
    retry: false,
  })

  const { data: logData } = useQuery({
    queryKey: ['report-log', sessionId],
    queryFn: () => api.getReportLog(sessionId!),
    enabled: !!sessionId,
    retry: false,
  })

  const logEvents: LogEvent[] = (logData?.events ?? []) as LogEvent[]

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card/50 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/reports"
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>К списку отчётов</span>
            </Link>
            <span className="text-muted-foreground">/</span>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              <span className="font-semibold text-foreground truncate max-w-[300px]">
                {report?.title ?? 'Просмотр отчёта'}
              </span>
            </div>
          </div>

          {report && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              {report.metadata?.llm_provider && (
                <span className="flex items-center gap-1">
                  <Cpu className="h-3 w-3" />
                  {report.metadata.llm_provider}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatDate(report.created_at)}
              </span>
            </div>
          )}
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-5xl">
        {isLoading && (
          <div className="flex items-center justify-center py-16 text-muted-foreground gap-3">
            <span className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
            <span>Загрузка отчёта...</span>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 flex flex-col items-center gap-3 text-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <p className="font-medium text-red-700">Не удалось загрузить отчёт</p>
            <p className="text-sm text-red-600">
              {(error as Error).message || 'Отчёт не найден или ещё не готов'}
            </p>
            <Link
              to="/reports"
              className="mt-2 inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm hover:bg-muted transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Назад к списку
            </Link>
          </div>
        )}

        {report && (
          <div className="space-y-6">
            {/* Report header */}
            <div className="rounded-xl border bg-card p-6 space-y-3">
              <h1 className="text-xl font-bold text-foreground">{report.title}</h1>
              <p className="text-sm text-muted-foreground">{report.query}</p>
              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1 flex-wrap">
                <span>Создан: {formatDate(report.created_at)}</span>
                {report.completed_at && <span>Завершён: {formatDate(report.completed_at)}</span>}
                {report.metadata?.total_tokens_used > 0 && (
                  <span>{report.metadata.total_tokens_used.toLocaleString()} токенов</span>
                )}
                {report.metadata?.llm_provider && (
                  <span className="bg-muted px-2 py-0.5 rounded font-mono">{report.metadata.llm_provider}</span>
                )}
              </div>
            </div>

            {/* Tab bar */}
            <div className="flex items-center gap-1 border-b">
              <button
                onClick={() => setActiveTab('report')}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'report'
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                Блоки отчёта
                {(report.blocks?.length ?? 0) > 0 && (
                  <span className="ml-1 text-xs bg-primary/10 text-primary px-1.5 rounded-full">
                    {report.blocks.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTab('log')}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'log'
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <ScrollText className="h-3.5 w-3.5" />
                Лог агентов
                {logEvents.length > 0 && (
                  <span className="ml-1 text-xs bg-muted text-muted-foreground px-1.5 rounded-full">
                    {logEvents.length}
                  </span>
                )}
              </button>
            </div>

            {activeTab === 'report' ? (
              /* Blocks */
              report.blocks && report.blocks.length > 0 ? (
                <div className="space-y-6">
                  {groupBlocks(report.blocks as ReportBlock[]).map((group, gi) =>
                    group.kind === 'kpi_grid' ? (
                      <div key={`grid-${gi}`} className={`grid gap-4 ${gridCols(group.blocks.length)}`}>
                        {group.blocks.map((block, idx) => (
                          <BlockErrorBoundary key={block.block_id ?? idx}>
                            <BlockRenderer block={block} />
                          </BlockErrorBoundary>
                        ))}
                      </div>
                    ) : (
                      <BlockErrorBoundary key={group.block.block_id}>
                        <BlockRenderer block={group.block} />
                      </BlockErrorBoundary>
                    )
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
                  <FileText className="h-10 w-10 text-muted-foreground" />
                  <p className="text-muted-foreground">В этом отчёте нет блоков</p>
                </div>
              )
            ) : (
              /* Agent log */
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <AgentLog
                  events={logEvents}
                  blackboardSnapshot={logData?.blackboard_snapshot as Record<string, unknown>}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
