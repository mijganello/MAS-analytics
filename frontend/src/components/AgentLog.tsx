import React, { useState, useMemo, useRef, useEffect } from 'react'
import {
  CheckCircle2, XCircle, AlertTriangle, Info, Zap, Play, SkipForward,
  ChevronDown, ChevronRight, Copy, Check, ListFilter,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LogEvent } from '@/app/store'

// ── Event metadata ────────────────────────────────────────────────────────────

const EVENT_META: Record<string, {
  label: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  bg: string
  dot: string
}> = {
  session_start:   { label: 'Сессия запущена',  icon: Play,           color: 'text-blue-600',    bg: 'bg-blue-50 dark:bg-blue-950/30',   dot: 'bg-blue-500' },
  plan_created:    { label: 'План создан',       icon: Zap,            color: 'text-violet-600',  bg: 'bg-violet-50 dark:bg-violet-950/30', dot: 'bg-violet-500' },
  group_start:     { label: 'Группа стартовала', icon: Play,           color: 'text-indigo-600',  bg: 'bg-indigo-50 dark:bg-indigo-950/30', dot: 'bg-indigo-400' },
  group_done:      { label: 'Группа завершена',  icon: CheckCircle2,   color: 'text-indigo-700',  bg: 'bg-indigo-50 dark:bg-indigo-950/30', dot: 'bg-indigo-500' },
  task_start:      { label: 'Задача запущена',   icon: Play,           color: 'text-sky-600',     bg: 'bg-sky-50 dark:bg-sky-950/30',     dot: 'bg-sky-400' },
  task_retry:      { label: 'Повтор',            icon: SkipForward,    color: 'text-amber-600',   bg: 'bg-amber-50 dark:bg-amber-950/30', dot: 'bg-amber-400' },
  task_escalated:  { label: 'Эскалация',         icon: AlertTriangle,  color: 'text-orange-600',  bg: 'bg-orange-50 dark:bg-orange-950/30', dot: 'bg-orange-500' },
  task_error:      { label: 'Ошибка задачи',     icon: XCircle,        color: 'text-red-600',     bg: 'bg-red-50 dark:bg-red-950/30',     dot: 'bg-red-500' },
  verdict_approved:{ label: 'Одобрено',          icon: CheckCircle2,   color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30', dot: 'bg-emerald-500' },
  verdict_rejected:{ label: 'Отклонено',         icon: XCircle,        color: 'text-rose-600',    bg: 'bg-rose-50 dark:bg-rose-950/30',   dot: 'bg-rose-500' },
  block_published: { label: 'Блок опубликован',  icon: CheckCircle2,   color: 'text-teal-600',    bg: 'bg-teal-50 dark:bg-teal-950/30',   dot: 'bg-teal-400' },
  assembly_start:  { label: 'Сборка отчёта',     icon: Zap,            color: 'text-purple-600',  bg: 'bg-purple-50 dark:bg-purple-950/30', dot: 'bg-purple-400' },
  session_complete:{ label: 'Сессия завершена',  icon: CheckCircle2,   color: 'text-green-700',   bg: 'bg-green-50 dark:bg-green-950/30', dot: 'bg-green-500' },
  session_error:   { label: 'Критическая ошибка',icon: XCircle,        color: 'text-red-700',     bg: 'bg-red-50 dark:bg-red-950/30',     dot: 'bg-red-600' },
  task_skipped:    { label: 'Задача пропущена',   icon: SkipForward,    color: 'text-slate-500',   bg: 'bg-slate-50 dark:bg-slate-950/30', dot: 'bg-slate-400' },
}

const DEFAULT_META = {
  label: 'Событие', icon: Info, color: 'text-muted-foreground', bg: 'bg-muted/30', dot: 'bg-muted-foreground',
}

const DEPT_LABELS: Record<string, string> = {
  data_extraction: 'Извлечение данных',
  quant_analysis: 'Кол. анализ',
  qual_analysis: 'Кач. анализ',
  visualization: 'Визуализация',
  report_assembly: 'Сборка отчёта',
}

// ── Helper ────────────────────────────────────────────────────────────────────

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

function hasDetails(details?: Record<string, unknown>) {
  return details && Object.keys(details).length > 0
}

// ── Single Event Row ─────────────────────────────────────────────────────────

const EventRow: React.FC<{ event: LogEvent; isLast: boolean }> = ({ event, isLast }) => {
  const [open, setOpen] = useState(false)
  const meta = EVENT_META[event.type] ?? DEFAULT_META
  const Icon = meta.icon
  const hasDetail = hasDetails(event.details)

  return (
    <div className="flex gap-3">
      {/* Timeline spine */}
      <div className="flex flex-col items-center flex-shrink-0 w-6">
        <div className={cn('w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5 ring-2 ring-background', meta.dot)} />
        {!isLast && <div className="w-px flex-1 bg-border mt-1" />}
      </div>

      {/* Content */}
      <div className={cn('flex-1 min-w-0 rounded-lg border px-3 py-2 mb-3', meta.bg)}>
        <div className="flex items-start gap-2">
          <Icon className={cn('h-3.5 w-3.5 flex-shrink-0 mt-0.5', meta.color)} />

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className={cn('text-xs font-semibold', meta.color)}>{meta.label}</span>
              <span className="text-xs font-medium text-foreground/80">{event.agent}</span>
              {event.department && (
                <span className="text-[10px] px-1.5 py-0 rounded-full bg-muted text-muted-foreground border">
                  {DEPT_LABELS[event.department] ?? event.department}
                </span>
              )}
              <span className="ml-auto text-[10px] text-muted-foreground font-mono flex-shrink-0">
                {formatTime(event.ts)}
              </span>
            </div>

            <p className="text-xs text-foreground/90 mt-0.5 leading-relaxed">{event.message}</p>

            {hasDetail && (
              <button
                onClick={() => setOpen(o => !o)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground mt-1 transition-colors"
              >
                {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                {open ? 'Скрыть детали' : 'Детали'}
              </button>
            )}

            {open && hasDetail && (
              <pre className="mt-2 text-[10px] leading-relaxed bg-background/60 rounded p-2 border overflow-x-auto text-muted-foreground max-h-48">
                {JSON.stringify(event.details, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Filter pill ───────────────────────────────────────────────────────────────

const FilterPill: React.FC<{
  label: string
  active: boolean
  onClick: () => void
}> = ({ label, active, onClick }) => (
  <button
    onClick={onClick}
    className={cn(
      'px-2.5 py-0.5 rounded-full text-[11px] font-medium border transition-colors',
      active
        ? 'bg-primary text-primary-foreground border-primary'
        : 'bg-muted text-muted-foreground border-transparent hover:border-border',
    )}
  >
    {label}
  </button>
)

// ── Main Component ────────────────────────────────────────────────────────────

type FilterKey = 'all' | 'approved' | 'rejected' | 'errors' | 'blocks'

interface Props {
  events: LogEvent[]
  blackboardSnapshot?: Record<string, unknown>
  /** When true, auto-scrolls to bottom on new events */
  autoScroll?: boolean
}

export const AgentLog: React.FC<Props> = ({ events, blackboardSnapshot, autoScroll = false }) => {
  const [filter, setFilter] = useState<FilterKey>('all')
  const [copied, setCopied] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [events.length, autoScroll])

  const filtered = useMemo(() => {
    switch (filter) {
      case 'approved': return events.filter(e => e.type === 'verdict_approved' || e.type === 'session_complete')
      case 'rejected': return events.filter(e => e.type === 'verdict_rejected' || e.type === 'task_retry' || e.type === 'task_escalated')
      case 'errors':   return events.filter(e => e.type === 'task_error' || e.type === 'session_error')
      case 'blocks':   return events.filter(e => e.type === 'block_published')
      default:         return events
    }
  }, [events, filter])

  const handleCopy = () => {
    const payload = JSON.stringify({ events, blackboard_snapshot: blackboardSnapshot }, null, 2)
    navigator.clipboard.writeText(payload).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="text-4xl mb-3">📋</div>
        <p className="text-sm text-muted-foreground">Лог агентов пуст</p>
        <p className="text-xs text-muted-foreground/60 mt-1">События появятся в ходе генерации</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <ListFilter className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
        <div className="flex flex-wrap gap-1.5">
          {([
            ['all',      `Все (${events.length})`],
            ['approved', 'Одобрено'],
            ['rejected', 'Отклонено'],
            ['errors',   'Ошибки'],
            ['blocks',   'Блоки'],
          ] as [FilterKey, string][]).map(([key, label]) => (
            <FilterPill key={key} label={label} active={filter === key} onClick={() => setFilter(key)} />
          ))}
        </div>

        <button
          onClick={handleCopy}
          className={cn(
            'ml-auto flex items-center gap-1.5 text-xs px-3 py-1 rounded-md border transition-all',
            copied
              ? 'bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/30'
              : 'bg-muted text-muted-foreground hover:text-foreground hover:border-border',
          )}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Скопировано' : 'Копировать JSON'}
        </button>
      </div>

      {/* Stats strip */}
      <div className="flex gap-4 text-[11px] text-muted-foreground px-1">
        <span>
          <span className="text-emerald-600 font-semibold">
            {events.filter(e => e.type === 'verdict_approved').length}
          </span> одобрено
        </span>
        <span>
          <span className="text-rose-600 font-semibold">
            {events.filter(e => e.type === 'verdict_rejected').length}
          </span> отклонено
        </span>
        <span>
          <span className="text-teal-600 font-semibold">
            {events.filter(e => e.type === 'block_published').length}
          </span> блоков
        </span>
        {events.filter(e => e.type === 'task_error').length > 0 && (
          <span>
            <span className="text-red-600 font-semibold">
              {events.filter(e => e.type === 'task_error').length}
            </span> ошибок
          </span>
        )}
      </div>

      {/* Timeline */}
      <div className="relative pt-1">
        {filtered.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-6">Нет событий по фильтру</p>
        ) : (
          filtered.map((event, i) => (
            <EventRow key={`${event.ts}-${i}`} event={event} isLast={i === filtered.length - 1} />
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
