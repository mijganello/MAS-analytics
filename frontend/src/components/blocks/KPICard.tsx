import React from 'react'
import { TrendingUp, TrendingDown, Minus, ShieldCheck, ShieldAlert } from 'lucide-react'
import type { KPICard } from '@/types/blocks'
import { cn, formatNumber } from '@/lib/utils'

export const KPICardComponent: React.FC<KPICard> = ({
  metric_name, value, unit, delta_pct, trend, is_positive_trend, verification_status, source_reference
}) => {
  const safeValue = typeof value === 'number' ? value : (parseFloat(String(value)) || 0)
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = is_positive_trend === true
    ? (trend === 'up' ? 'text-emerald-600' : 'text-red-500')
    : is_positive_trend === false
    ? (trend === 'down' ? 'text-emerald-600' : 'text-red-500')
    : 'text-muted-foreground'

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm flex flex-col h-full">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground leading-snug">{metric_name ?? 'Показатель'}</p>
        <div className="flex-shrink-0 mt-0.5">
          {verification_status === 'unverified' ? (
            <ShieldAlert className="h-4 w-4 text-amber-500" aria-label="Данные не верифицированы" />
          ) : (
            <ShieldCheck className="h-4 w-4 text-emerald-500" aria-label="Данные верифицированы" />
          )}
        </div>
      </div>
      <div className="mt-auto pt-3 flex items-end gap-2">
        <span className="text-3xl font-bold tracking-tight text-foreground">
          {formatNumber(safeValue)}
        </span>
        {unit && <span className="text-sm text-muted-foreground mb-1">{unit}</span>}
      </div>
      {delta_pct !== undefined && delta_pct !== null && (
        <div className={cn('flex items-center gap-1 mt-2 text-sm font-medium', trendColor)}>
          <TrendIcon className="h-4 w-4" />
          <span>{delta_pct > 0 ? '+' : ''}{formatNumber(delta_pct, 1)}%</span>
          <span className="text-muted-foreground font-normal text-xs">к пред. периоду</span>
        </div>
      )}
      {source_reference && (
        <p className="text-xs text-muted-foreground mt-2 truncate" title={source_reference}>
          {source_reference}
        </p>
      )}
    </div>
  )
}
