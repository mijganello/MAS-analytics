import React, { useState } from 'react'
import { Download } from 'lucide-react'
import type { TableBlock } from '@/types/blocks'
import { cn, formatNumber } from '@/lib/utils'

const PAGE_SIZE = 10

export const TableBlockComponent: React.FC<TableBlock> = ({
  title, columns, rows, totals_row, exportable
}) => {
  const [page, setPage] = useState(0)
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const safeColumns = Array.isArray(columns) ? columns : []
  const safeRows = Array.isArray(rows) ? rows : []

  const sorted = [...safeRows].sort((a, b) => {
    if (!sortCol) return 0
    const av = a[sortCol], bv = b[sortCol]
    const cmp = String(av).localeCompare(String(bv), 'ru', { numeric: true })
    return sortDir === 'asc' ? cmp : -cmp
  })

  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(safeRows.length / PAGE_SIZE)

  const handleSort = (key: string, sortable: boolean) => {
    if (!sortable) return
    if (sortCol === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(key); setSortDir('asc') }
  }

  const exportCSV = () => {
    const headers = safeColumns.map(c => c.label).join(',')
    const rowStrs = safeRows.map(r => safeColumns.map(c => `"${r[c.key] ?? ''}"`).join(','))
    const csv = [headers, ...rowStrs].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${title || 'table'}.csv`
    a.click()
  }

  const formatCell = (val: unknown, dtype: string): string => {
    if (val === null || val === undefined) return '—'
    if (dtype === 'number' || dtype === 'currency' || dtype === 'percent') {
      const n = parseFloat(String(val))
      if (isNaN(n)) return String(val)
      return dtype === 'percent' ? `${formatNumber(n, 1)}%` : formatNumber(n)
    }
    return String(val)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        {title && <h3 className="font-semibold text-foreground">{title}</h3>}
        {exportable && (
          <button onClick={exportCSV} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <Download className="h-3 w-3" /> CSV
          </button>
        )}
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              {safeColumns.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key, col.sortable)}
                  className={cn(
                    'px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap',
                    col.sortable && 'cursor-pointer hover:text-foreground select-none'
                  )}
                >
                  {col.label}
                  {col.unit && <span className="text-xs ml-1">({col.unit})</span>}
                  {sortCol === col.key && <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((row, i) => (
              <tr key={i} className="border-t hover:bg-muted/30 transition-colors">
                {safeColumns.map(col => (
                  <td key={col.key} className="px-3 py-2 text-foreground">
                    {formatCell(row[col.key], col.dtype)}
                  </td>
                ))}
              </tr>
            ))}
            {totals_row && (
              <tr className="border-t bg-muted/40 font-semibold">
                {safeColumns.map(col => (
                  <td key={col.key} className="px-3 py-2">
                    {formatCell(totals_row[col.key], col.dtype)}
                  </td>
                ))}
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Строки {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, safeRows.length)} из {safeRows.length}</span>
          <div className="flex gap-2">
            <button disabled={page === 0} onClick={() => setPage(p => p - 1)}
              className="px-2 py-1 rounded border disabled:opacity-40 hover:bg-muted transition-colors">←</button>
            <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}
              className="px-2 py-1 rounded border disabled:opacity-40 hover:bg-muted transition-colors">→</button>
          </div>
        </div>
      )}
    </div>
  )
}
