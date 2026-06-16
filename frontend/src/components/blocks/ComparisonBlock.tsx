import React from 'react'
import type { ComparisonBlock } from '@/types/blocks'
import { formatNumber } from '@/lib/utils'

export const ComparisonBlockComponent: React.FC<ComparisonBlock> = ({
  title, items, dimensions, winner, analysis
}) => {
  const safeItems = Array.isArray(items) ? items : []
  const safeDimensions = Array.isArray(dimensions) ? dimensions : []
  const cols = Math.min(safeItems.length || 1, 3)

  return (
    <div className="space-y-3">
      {title && <h3 className="font-semibold text-foreground">{title}</h3>}
      {safeItems.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">Нет данных для сравнения</p>
      ) : (
        <div
          className="grid gap-3"
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
          {safeItems.map((item, i) => (
            <div
              key={i}
              className={`rounded-xl border p-4 space-y-2 ${
                item.label === winner ? 'border-primary ring-1 ring-primary bg-primary/5' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-sm text-foreground">{item.label ?? `Объект ${i + 1}`}</h4>
                {item.label === winner && (
                  <span className="text-xs text-primary font-semibold">★ Лучший</span>
                )}
              </div>
              {safeDimensions.map(dim => (
                <div key={dim} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{dim}</span>
                  <span className="font-medium text-foreground">
                    {typeof item.metrics?.[dim] === 'number'
                      ? formatNumber(item.metrics[dim] as number)
                      : String(item.metrics?.[dim] ?? '—')}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
      {analysis && <p className="text-sm text-muted-foreground">{analysis}</p>}
    </div>
  )
}
