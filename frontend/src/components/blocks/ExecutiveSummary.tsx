import React from 'react'
import { CheckCircle2, ArrowRight } from 'lucide-react'
import type { ExecutiveSummaryBlock } from '@/types/blocks'

export const ExecutiveSummaryComponent: React.FC<ExecutiveSummaryBlock> = ({
  key_findings, recommendations, overall_conclusion, report_quality_score
}) => {
  const findings = Array.isArray(key_findings) ? key_findings : []
  const recs = Array.isArray(recommendations) ? recommendations : []
  const score = typeof report_quality_score === 'number' ? report_quality_score : 0

  return (
    <div className="rounded-xl border bg-gradient-to-br from-primary/5 to-background p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-foreground">Исполнительное резюме</h3>
        {score > 0 && (
          <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
            Качество: {Math.round(score * 100)}%
          </span>
        )}
      </div>

      {findings.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-foreground">Ключевые выводы</h4>
          <ul className="space-y-1.5">
            {findings.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {recs.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-foreground">Рекомендации</h4>
          <ul className="space-y-1.5">
            {recs.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <ArrowRight className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {overall_conclusion && (
        <div className="border-t pt-4">
          <p className="text-sm text-foreground font-medium leading-relaxed">{overall_conclusion}</p>
        </div>
      )}
    </div>
  )
}
