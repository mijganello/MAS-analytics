import React, { useEffect, useState, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BarChart3, Clock, ChevronLeft, ChevronRight, FileText, CheckCircle2, Loader2, PlusSquare } from 'lucide-react'
import { api } from '@/lib/api'
import type { ReportListItem } from '@/lib/api'
import { cn } from '@/lib/utils'

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  complete: CheckCircle2,
  completed: CheckCircle2,
  running: Loader2,
  failed: FileText,
}

const STATUS_COLOR: Record<string, string> = {
  complete: 'text-emerald-600',
  completed: 'text-emerald-600',
  running: 'text-primary animate-spin',
  failed: 'text-destructive',
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'только что'
  if (min < 60) return `${min} мин назад`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} ч назад`
  return `${Math.floor(h / 24)} дн назад`
}

interface Props {
  collapsed: boolean
  onToggle: () => void
  onNewChat: () => void
  currentSessionId: string | null
}

export const ReportsSidebar: React.FC<Props> = ({ collapsed, onToggle, onNewChat, currentSessionId }) => {
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(false)
  const location = useLocation()

  const fetchReports = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.listReports()
      setReports(data)
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchReports()
  }, [fetchReports, currentSessionId])

  return (
    <aside
      className={cn(
        'flex flex-col shrink-0 border-r bg-muted transition-all duration-300 ease-in-out overflow-hidden',
        collapsed ? 'w-12' : 'w-64',
      )}
    >
      {/* Top bar */}
      <div className={cn(
        'flex items-center border-b h-12 shrink-0 px-2',
        collapsed ? 'justify-center' : 'justify-between px-3',
      )}>
        {!collapsed && (
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary shrink-0" />
            <span className="font-semibold text-sm text-foreground truncate">Отчёты</span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
          title={collapsed ? 'Развернуть' : 'Свернуть'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* New chat button */}
      <div className={cn('px-2 py-2 shrink-0', collapsed && 'flex justify-center')}>
        <button
          onClick={onNewChat}
          className={cn(
            'flex items-center gap-2 rounded-xl transition-colors text-sm font-medium',
            'text-primary hover:bg-primary/10 active:bg-primary/20',
            collapsed
              ? 'h-8 w-8 justify-center'
              : 'w-full px-3 py-2',
          )}
          title="Новый анализ"
        >
          <PlusSquare className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Новый анализ</span>}
        </button>
      </div>

      {/* Reports list */}
      <div className="flex-1 overflow-y-auto space-y-0.5 px-1.5 pb-2">
        {loading && !reports.length && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        )}

        {!collapsed && reports.map(r => {
          const isActive = r.report_id === currentSessionId
          const Icon = STATUS_ICON[r.status] ?? FileText
          const iconCls = STATUS_COLOR[r.status] ?? 'text-muted-foreground'

          return (
            <Link
              key={r.report_id}
              to={`/reports/${r.report_id}`}
        className={cn(
            'flex items-start gap-2.5 rounded-2xl px-2.5 py-2 text-xs transition-colors group',
                isActive
                  ? 'bg-primary/15 text-foreground'
                  : 'text-muted-foreground hover:bg-muted-foreground/15 hover:text-foreground',
              )}
            >
              <Icon className={cn('h-3.5 w-3.5 shrink-0 mt-0.5', iconCls)} />
              <div className="min-w-0 flex-1">
                <p className="font-medium leading-snug line-clamp-2 text-foreground">
                  {r.query}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Clock className="h-2.5 w-2.5" />
                  <span>{relativeTime(r.created_at)}</span>
                  <span className="text-muted-foreground/50">·</span>
                  <span>{r.llm_provider}</span>
                </div>
              </div>
            </Link>
          )
        })}

        {!collapsed && !loading && reports.length === 0 && (
          <p className="text-xs text-muted-foreground px-2 py-3 text-center">
            Отчётов пока нет
          </p>
        )}

        {/* Icons-only mode: just status dots */}
        {collapsed && reports.slice(0, 8).map(r => {
          const Icon = STATUS_ICON[r.status] ?? FileText
          const iconCls = STATUS_COLOR[r.status] ?? 'text-muted-foreground'
          return (
            <Link
              key={r.report_id}
              to={`/reports/${r.report_id}`}
              className="flex items-center justify-center h-8 rounded-lg hover:bg-muted transition-colors"
              title={r.query}
            >
              <Icon className={cn('h-3.5 w-3.5', iconCls)} />
            </Link>
          )
        })}
      </div>
    </aside>
  )
}
