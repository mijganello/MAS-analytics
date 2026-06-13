import React from 'react'
import { CheckCircle2, Loader2, AlertCircle, Clock } from 'lucide-react'
import { useStore } from '@/app/store'
import { cn } from '@/lib/utils'

const deptLabels: Record<string, string> = {
  data_extraction: 'Извлечение данных',
  quant_analysis: 'Количественный анализ',
  qual_analysis: 'Качественный анализ',
  visualization: 'Визуализация',
  report_assembly: 'Сборка отчёта',
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
  pending: 'text-muted-foreground',
  escalated: 'text-amber-600',
  review: 'text-blue-500',
}

export const AgentMonitor: React.FC = () => {
  const { taskStatuses, isGenerating, blocks } = useStore()

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
