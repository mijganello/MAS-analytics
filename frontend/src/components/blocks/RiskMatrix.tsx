import React from 'react'
import type { RiskMatrixBlock, RiskItem } from '@/types/blocks'
import { cn } from '@/lib/utils'

const levelColor: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  medium: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  high: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
}

const levelLabel: Record<string, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
}

const overallColor: Record<string, string> = {
  low: 'text-emerald-600',
  medium: 'text-amber-600',
  high: 'text-red-600',
  critical: 'text-red-700 font-bold',
}

const overallLabel: Record<string, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
  critical: 'КРИТИЧЕСКИЙ',
}

const RiskBadge: React.FC<{ level?: string }> = ({ level }) => {
  const safeLevel = level && levelColor[level] ? level : 'medium'
  return (
    <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', levelColor[safeLevel])}>
      {levelLabel[safeLevel] ?? safeLevel}
    </span>
  )
}

export const RiskMatrixBlockComponent: React.FC<RiskMatrixBlock> = ({
  risks, overall_risk_level, title
}) => {
  const safeLevel = overall_risk_level && overallColor[overall_risk_level]
    ? overall_risk_level
    : 'medium'
  const safeRisks: RiskItem[] = Array.isArray(risks) ? risks : []

  return (
    <div className="space-y-4">
      {title && <h3 className="font-semibold text-foreground">{title}</h3>}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Общий уровень риска:</span>
        <span className={cn('font-semibold', overallColor[safeLevel])}>
          {overallLabel[safeLevel] ?? safeLevel}
        </span>
      </div>
      {safeRisks.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">Риски не определены</p>
      ) : (
        <div className="space-y-3">
          {safeRisks.map((risk, i) => (
            <div key={i} className="rounded-lg border p-4 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <h4 className="font-medium text-foreground text-sm">{risk.name ?? '—'}</h4>
                <div className="flex gap-2 flex-shrink-0 items-center">
                  <span className="text-xs text-muted-foreground">Вер.:</span>
                  <RiskBadge level={risk.probability} />
                  <span className="text-xs text-muted-foreground">Влияние:</span>
                  <RiskBadge level={risk.impact} />
                </div>
              </div>
              {risk.description && (
                <p className="text-xs text-muted-foreground">{risk.description}</p>
              )}
              {risk.mitigation && (
                <p className="text-xs text-emerald-700 dark:text-emerald-400">
                  ✓ Митигация: {risk.mitigation}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
