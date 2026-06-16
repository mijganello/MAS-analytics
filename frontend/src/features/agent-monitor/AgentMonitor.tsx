import React from 'react'
import { CheckCircle2, Loader2, AlertCircle, Clock } from 'lucide-react'
import { useStore } from '@/app/store'
import { cn } from '@/lib/utils'

const deptLabels: Record<string, string> = {
  data_extraction: 'Извлечение',
  quant_analysis: 'Анализ',
  qual_analysis: 'Качественный',
  visualization: 'Визуализация',
  report_assembly: 'Сборка',
}

const statusIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  approved: CheckCircle2,
  running: Loader2,
  failed: AlertCircle,
  pending: Clock,
  escalated: AlertCircle,
  review: Loader2,
}

const statusColors: Record<string, string> = {
  approved: 'text-emerald-600',
  running: 'text-primary animate-spin',
  failed: 'text-destructive',
  pending: 'text-muted-foreground/50',
  escalated: 'text-amber-500',
  review: 'text-blue-500',
}

const dotColors: Record<string, string> = {
  approved: 'bg-emerald-500',
  running: 'bg-primary animate-pulse',
  failed: 'bg-destructive',
  pending: 'bg-muted-foreground/30',
  escalated: 'bg-amber-500',
  review: 'bg-blue-500',
}

interface Props {
  compact?: boolean
}

export const AgentMonitor: React.FC<Props> = ({ compact = false }) => {
  const { taskStatuses, isGenerating, blocks } = useStore()

  /* ── Compact mode: horizontal status strip ── */
  if (compact) {
    const active = taskStatuses.filter(t => t.status === 'running' || t.status === 'review')
    const done   = taskStatuses.filter(t => t.status === 'approved').length
    const total  = taskStatuses.length

    return (
      <div className="flex items-center gap-3 text-xs text-muted-foreground overflow-x-auto no-scrollbar">
        {/* Task dots */}
        <div className="flex items-center gap-1 shrink-0">
          {taskStatuses.map(task => {
            const dotCls = dotColors[task.status] ?? 'bg-muted-foreground/30'
            return (
              <span
                key={task.task_id}
                title={`${deptLabels[task.department] ?? task.department} — ${task.status}`}
                className={cn('h-2 w-2 rounded-full shrink-0', dotCls)}
              />
            )
          })}
        </div>

        {/* Active task name */}
        {active.length > 0 ? (
          <span className="flex items-center gap-1.5 shrink-0">
            <Loader2 className="h-3 w-3 text-primary animate-spin" />
            <span className="text-foreground font-medium">
              {deptLabels[active[0].department] ?? active[0].department}
            </span>
          </span>
        ) : isGenerating ? (
          <span className="flex items-center gap-1.5 shrink-0 text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
            Обработка...
          </span>
        ) : null}

        {/* Progress */}
        {total > 0 && (
          <span className="ml-auto shrink-0 font-medium tabular-nums">
            {done}/{total} задач
          </span>
        )}

        {/* Blocks count */}
        {blocks.length > 0 && (
          <span className="shrink-0 text-muted-foreground/70">
            · {blocks.length} блоков
          </span>
        )}
      </div>
    )
  }

  /* ── Full mode (vertical list) ── */
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Агенты</h3>
        {isGenerating && (
          <span className="flex items-center gap-1.5 text-xs text-primary">
            <span className="animate-pulse h-2 w-2 bg-primary rounded-full" />
            Генерация...
          </span>
        )}
      </div>

      {taskStatuses.length === 0 && !isGenerating ? (
        <p className="text-xs text-muted-foreground">Задачи появятся здесь</p>
      ) : (
        <div className="space-y-2">
          {taskStatuses.map(task => {
            const Icon = statusIcons[task.status] || Clock
            const color = statusColors[task.status] || 'text-muted-foreground'
            return (
              <div key={task.task_id} className="flex items-start gap-2 text-xs">
                <Icon className={cn('h-3.5 w-3.5 flex-shrink-0 mt-0.5', color)} />
                <div className="min-w-0">
                  <p className="font-medium text-foreground truncate">
                    {deptLabels[task.department] || task.department}
                  </p>
                  <p className="text-muted-foreground">{task.status}</p>
                  {task.tokens_used ? <p className="text-muted-foreground">{task.tokens_used} токенов</p> : null}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="border-t pt-3">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Блоков готово</span>
          <span className="font-medium text-foreground">{blocks.length}</span>
        </div>
      </div>
    </div>
  )
}
