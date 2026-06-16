import React from 'react'
import { AlertTriangle, TrendingUp, Lightbulb, AlertCircle, Target } from 'lucide-react'
import type { InsightBlock } from '@/types/blocks'
import { cn } from '@/lib/utils'

const icons: Record<string, React.ElementType> = {
  finding: TrendingUp,
  anomaly: AlertTriangle,
  recommendation: Lightbulb,
  risk: AlertCircle,
  opportunity: Target,
}

const severityStyles: Record<string, string> = {
  info: 'border-blue-500 bg-blue-100 dark:border-blue-600 dark:bg-blue-950/50',
  warning: 'border-amber-500 bg-amber-100 dark:border-amber-600 dark:bg-amber-950/50',
  critical: 'border-red-600 bg-red-100 dark:border-red-700 dark:bg-red-950/50',
}

const iconColors: Record<string, string> = {
  info: 'text-blue-800',
  warning: 'text-amber-800',
  critical: 'text-red-800',
}

export const InsightBlockComponent: React.FC<InsightBlock> = ({
  headline, explanation, insight_type, severity, confidence
}) => {
  const safeSeverity = severity && severityStyles[severity] ? severity : 'info'
  const Icon = (insight_type && icons[insight_type]) ? icons[insight_type] : Lightbulb
  const safeConfidence = typeof confidence === 'number' ? confidence : null

  return (
    <div className={cn('rounded-2xl border p-4 space-y-2', severityStyles[safeSeverity])}>
      <div className="flex items-start gap-3">
        <Icon className={cn('h-5 w-5 flex-shrink-0 mt-0.5', iconColors[safeSeverity])} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-semibold text-foreground">{headline ?? 'Инсайт'}</h4>
            {safeConfidence !== null && (
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {Math.round(safeConfidence * 100)}%
              </span>
            )}
          </div>
          {explanation && (
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{explanation}</p>
          )}
        </div>
      </div>
    </div>
  )
}
