import React, { useMemo } from 'react'
import { BlockRenderer } from '@/components/blocks/BlockRenderer'
import { BlockErrorBoundary } from '@/components/BlockErrorBoundary'
import { useStore } from '@/app/store'
import type { ReportBlock } from '@/types/blocks'

const DEPT_LABELS: Record<string, string> = {
  data_extraction: 'Извлечение данных',
  quant_analysis: 'Количественный анализ',
  qual_analysis: 'Качественный анализ',
  visualization: 'Визуализация',
  report_assembly: 'Сборка отчёта',
}

// Group consecutive kpi_card blocks together; all other blocks stay solo.
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

/* ── Live agent activity indicator ── */
const AgentActivity: React.FC = () => {
  const { logEvents, taskStatuses } = useStore()

  const latest = useMemo(() => {
    const meaningful = logEvents.filter(e =>
      ['task_start', 'llm_response', 'tool_call', 'nlp_analysis',
       'context_loaded', 'verdict_approved', 'verdict_rejected',
       'group_start', 'assembly_start'].includes(e.type)
    )
    return meaningful.slice(-1)[0] ?? null
  }, [logEvents])

  const running = taskStatuses.filter(t => t.status === 'running' || t.status === 'review')
  const done    = taskStatuses.filter(t => t.status === 'approved').length
  const total   = taskStatuses.length

  const progress = total > 0 ? (done / total) : 0

  const deptLabel = latest?.department
    ? DEPT_LABELS[latest.department] ?? latest.department
    : running[0]?.department
      ? DEPT_LABELS[running[0].department] ?? running[0].department
      : 'Обработка'

  const agentLabel = latest?.agent ?? running[0]?.task_id ?? ''

  const msg = latest?.message ?? 'Агенты инициализируются...'

  return (
    <div className="rounded-2xl border bg-card p-5 space-y-4 animate-in fade-in duration-500">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {/* Animated dots */}
          <div className="flex gap-1">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="h-2 w-2 rounded-full bg-primary"
                style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
              />
            ))}
          </div>
          <span className="text-sm font-medium text-foreground">{deptLabel}</span>
          {agentLabel && (
            <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5 hidden sm:inline">
              {agentLabel}
            </span>
          )}
        </div>
        {total > 0 && (
          <span className="text-xs text-muted-foreground tabular-nums">
            {done}/{total} задач
          </span>
        )}
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="h-1 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
            style={{ width: `${Math.max(5, progress * 100)}%` }}
          />
        </div>
      )}

      {/* Latest message */}
      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
        {msg}
      </p>

      {/* Active tasks pills */}
      {running.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {running.map(t => (
            <span key={t.task_id} className="flex items-center gap-1 text-[11px] bg-primary/10 text-primary rounded-full px-2 py-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
              {DEPT_LABELS[t.department] ?? t.department}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export const ReportCanvas: React.FC = () => {
  const { blocks, isGenerating } = useStore()

  if (blocks.length === 0 && !isGenerating) return null

  const groups = groupBlocks(blocks)

  return (
    <div className="space-y-6">
      {groups.map((group, gi) =>
        group.kind === 'kpi_grid' ? (
          <div
            key={`grid-${gi}`}
            className={`grid gap-4 ${gridCols(group.blocks.length)} animate-in fade-in slide-in-from-bottom-2 duration-300`}
          >
            {group.blocks.map(block => (
              <BlockErrorBoundary key={block.block_id}>
                <BlockRenderer block={block} />
              </BlockErrorBoundary>
            ))}
          </div>
        ) : (
          <div
            key={group.block.block_id}
            className="animate-in fade-in slide-in-from-bottom-2 duration-300"
          >
            <BlockErrorBoundary>
              <BlockRenderer block={group.block} />
            </BlockErrorBoundary>
          </div>
        )
      )}

      {isGenerating && <AgentActivity />}
    </div>
  )
}
