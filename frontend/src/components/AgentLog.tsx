import React, { useState, useMemo, useRef, useEffect } from 'react'
import {
  CheckCircle2, XCircle, AlertTriangle, Info, Zap, Play, SkipForward,
  ChevronDown, ChevronRight, Copy, Check, ListFilter, Database, Cpu,
  BarChart2, FileText, Brain, Search, Wrench,
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
  autoExpand?: boolean
}> = {
  session_start:    { label: 'Сессия запущена',        icon: Play,         color: 'text-blue-800',    bg: 'bg-blue-100',     dot: 'bg-blue-700' },
  plan_created:     { label: 'План составлен',          icon: Brain,        color: 'text-violet-800',  bg: 'bg-violet-100',   dot: 'bg-violet-700', autoExpand: true },
  group_start:      { label: 'Группа стартовала',       icon: Play,         color: 'text-indigo-800',  bg: 'bg-indigo-100',   dot: 'bg-indigo-600' },
  group_done:       { label: 'Группа завершена',        icon: CheckCircle2, color: 'text-indigo-900',  bg: 'bg-indigo-100',   dot: 'bg-indigo-700' },
  task_start:       { label: 'Задача запущена',         icon: Play,         color: 'text-sky-800',     bg: 'bg-sky-100',      dot: 'bg-sky-600' },
  context_loaded:   { label: 'Контекст загружен',       icon: Search,       color: 'text-cyan-800',    bg: 'bg-cyan-100',     dot: 'bg-cyan-600', autoExpand: true },
  tool_call:        { label: 'Вызов инструмента',       icon: Wrench,       color: 'text-teal-800',    bg: 'bg-teal-100',     dot: 'bg-teal-600', autoExpand: true },
  nlp_analysis:     { label: 'NLP-анализ',              icon: FileText,     color: 'text-emerald-800', bg: 'bg-emerald-100',  dot: 'bg-emerald-600', autoExpand: true },
  llm_response:     { label: 'LLM завершил задачу',     icon: Cpu,          color: 'text-blue-900',    bg: 'bg-blue-100',     dot: 'bg-blue-800', autoExpand: true },
  task_retry:       { label: 'Повтор попытки',          icon: SkipForward,  color: 'text-amber-800',   bg: 'bg-amber-100',    dot: 'bg-amber-600' },
  task_escalated:   { label: 'Эскалация',               icon: AlertTriangle,color: 'text-orange-800',  bg: 'bg-orange-100',   dot: 'bg-orange-700' },
  task_error:       { label: 'Ошибка задачи',           icon: XCircle,      color: 'text-red-800',     bg: 'bg-red-100',      dot: 'bg-red-700' },
  verdict_approved: { label: 'Критик: Одобрено',        icon: CheckCircle2, color: 'text-emerald-800', bg: 'bg-emerald-100',  dot: 'bg-emerald-700', autoExpand: true },
  verdict_rejected: { label: 'Критик: Отклонено',       icon: XCircle,      color: 'text-rose-800',    bg: 'bg-rose-100',     dot: 'bg-rose-700', autoExpand: true },
  block_published:  { label: 'Блок опубликован',        icon: BarChart2,    color: 'text-teal-800',    bg: 'bg-teal-100',     dot: 'bg-teal-600' },
  assembly_start:   { label: 'Сборка отчёта',           icon: Zap,          color: 'text-purple-800',  bg: 'bg-purple-100',   dot: 'bg-purple-600' },
  session_complete: { label: 'Сессия завершена',        icon: CheckCircle2, color: 'text-green-900',   bg: 'bg-green-100',    dot: 'bg-green-700', autoExpand: true },
  session_error:    { label: 'Критическая ошибка',      icon: XCircle,      color: 'text-red-900',     bg: 'bg-red-100',      dot: 'bg-red-800', autoExpand: true },
  task_skipped:     { label: 'Задача пропущена',        icon: SkipForward,  color: 'text-slate-700',   bg: 'bg-slate-100',    dot: 'bg-slate-600' },
}

const DEFAULT_META = {
  label: 'Событие', icon: Info, color: 'text-muted-foreground', bg: 'bg-muted/30', dot: 'bg-muted-foreground',
}

const DEPT_LABELS: Record<string, string> = {
  data_extraction:  'Данные',
  quant_analysis:   'Квант. анализ',
  qual_analysis:    'Кач. анализ',
  visualization:    'Визуализация',
  report_assembly:  'Сборка',
  orchestrator:     'Оркестратор',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

function shortId(id?: string | null): string {
  return id ? id.slice(0, 8) : ''
}

// ── Specialised detail renderers ──────────────────────────────────────────────

const PlanDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => {
  const tasks = d.tasks as { id: string; dept: string; desc: string }[] | undefined
  const groups = d.groups as string[][] | undefined
  return (
    <div className="space-y-3">
      {!!d.reasoning && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Рассуждение планировщика</p>
          <p className="text-xs text-foreground leading-relaxed">{String(d.reasoning)}</p>
        </div>
      )}
      {tasks && tasks.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
            Задачи ({tasks.length})
          </p>
          <div className="space-y-1">
            {tasks.map((t, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="text-muted-foreground font-mono w-4 flex-shrink-0">{i + 1}.</span>
                <span className="px-1 py-0 rounded text-[10px] font-medium bg-primary/10 text-primary flex-shrink-0">
                  {DEPT_LABELS[t.dept] ?? t.dept}
                </span>
                <span className="text-foreground">{t.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {groups && groups.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
            Группы выполнения
          </p>
          <div className="flex flex-wrap gap-1">
            {groups.map((g, i) => (
              <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground border">
                Группа {i + 1}: {g.length} задач
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const ContextDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => {
  const sources = d.sources as string[] | undefined
  const headers = d.chunk_headers as string[] | undefined
  return (
    <div className="space-y-2">
      <div className="flex gap-4 text-xs">
        <span><span className="font-semibold text-foreground">{String(d.chunks_count ?? 0)}</span> фрагментов</span>
        <span><span className="font-semibold text-foreground">{sources?.length ?? 0}</span> источников</span>
      </div>
      {sources && sources.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Источники</p>
          <div className="flex flex-wrap gap-1">
            {sources.map((s, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0 rounded bg-muted text-muted-foreground border">{s}</span>
            ))}
          </div>
        </div>
      )}
      {headers && headers.filter(Boolean).length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Разделы</p>
          <div className="flex flex-wrap gap-1">
            {headers.filter(Boolean).map((h, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0 rounded bg-muted text-foreground/70 border">{h}</span>
            ))}
          </div>
        </div>
      )}
      {!!d.top_chunk_preview && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Фрагмент контекста</p>
          <p className="text-[10px] text-muted-foreground leading-relaxed bg-background rounded p-2 border">
            {String(d.top_chunk_preview)}
          </p>
        </div>
      )}
    </div>
  )
}

const ToolCallDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => {
  const calcs = d.calculations as Record<string, unknown> | undefined
  const series = d.numeric_series as Record<string, unknown> | undefined
  const chartSuggestion = d.chart_suggestion as Record<string, unknown> | undefined
  return (
    <div className="space-y-2">
      {chartSuggestion && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Рекомендации по графику</p>
          <pre className="text-[10px] bg-background rounded p-2 border overflow-x-auto max-h-32 text-foreground/80">
            {JSON.stringify(chartSuggestion, null, 2)}
          </pre>
        </div>
      )}
      {!!d.data_sources && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Источники данных</p>
          <div className="flex flex-wrap gap-1">
            {(d.data_sources as string[]).map((s, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0 rounded bg-muted text-foreground/70 border">{s}</span>
            ))}
          </div>
        </div>
      )}
      {series && Object.keys(series).length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Числовые ряды</p>
          <div className="space-y-1">
            {Object.entries(series).slice(0, 8).map(([name, info]) => {
              const inf = info as { count?: number; values?: number[] }
              return (
                <div key={name} className="flex items-start gap-2 text-[10px]">
                  <span className="font-medium text-foreground/70 min-w-[80px] truncate">{name}:</span>
                  <span className="text-muted-foreground">
                    {inf.count} значений
                    {inf.values && ` [${inf.values.slice(0, 4).join(', ')}${inf.values.length > 4 ? ', …' : ''}]`}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
      {calcs && Object.keys(calcs).length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
            Результаты вычислений ({Object.keys(calcs).length})
          </p>
          <div className="space-y-1.5">
            {Object.entries(calcs).slice(0, 10).map(([key, val]) => (
              <div key={key}>
                <p className="text-[10px] font-medium text-foreground/70 mb-0.5">{key}</p>
                <pre className="text-[10px] bg-background rounded p-1.5 border overflow-x-auto text-muted-foreground max-h-24">
                  {typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val)}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const NLPDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => {
  const sentiment = d.sentiment as Record<string, unknown> | null | undefined
  const keywords = d.keywords as (string | Record<string, unknown>)[] | null | undefined
  const risks = d.risks as Record<string, unknown> | null | undefined
  const summary = d.extractive_summary as unknown
  return (
    <div className="space-y-2">
      {!!d.text_length_chars && (
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span>Проанализировано: <span className="font-semibold text-foreground">{Number(d.text_length_chars).toLocaleString('ru')}</span> симв.</span>
          <span>Фрагментов: <span className="font-semibold text-foreground">{String(d.chunks_analyzed)}</span></span>
        </div>
      )}
      {sentiment && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Тональность</p>
          <pre className="text-[10px] bg-background rounded p-2 border overflow-x-auto text-foreground/80 max-h-24">
            {JSON.stringify(sentiment, null, 2)}
          </pre>
        </div>
      )}
      {keywords && keywords.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Ключевые слова</p>
          <div className="flex flex-wrap gap-1">
            {keywords.slice(0, 20).map((kw, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0 rounded-full bg-primary/10 text-primary border border-primary/20">
                {typeof kw === 'string' ? kw : JSON.stringify(kw)}
              </span>
            ))}
          </div>
        </div>
      )}
      {!!summary && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Экстрактивное резюме</p>
          <p className="text-[10px] text-muted-foreground leading-relaxed bg-background rounded p-2 border">
            {typeof summary === 'string' ? summary : JSON.stringify(summary)}
          </p>
        </div>
      )}
      {risks && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Факторы риска</p>
          <pre className="text-[10px] bg-background rounded p-2 border overflow-x-auto text-foreground/80 max-h-32">
            {JSON.stringify(risks, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

const LLMResponseDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => {
  const blocks = d.blocks as { type?: string; title?: string }[] | undefined
  const blockOrder = d.block_order as { type?: string; title?: string }[] | undefined
  const list = blocks ?? blockOrder
  return (
    <div className="space-y-2">
      {!!d.reasoning && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Рассуждение агента</p>
          <p className="text-xs text-foreground leading-relaxed bg-background rounded p-2 border">{String(d.reasoning)}</p>
        </div>
      )}
      {!!d.data_quality_notes && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Заметки о качестве данных</p>
          <p className="text-xs text-muted-foreground leading-relaxed">{String(d.data_quality_notes)}</p>
        </div>
      )}
      {!!d.key_findings && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Ключевые выводы</p>
          <ul className="space-y-0.5">
            {(d.key_findings as string[]).map((f, i) => (
              <li key={i} className="text-xs text-foreground flex gap-1.5">
                <span className="text-primary flex-shrink-0">•</span> {f}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!!d.recommendations && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Рекомендации</p>
          <ul className="space-y-0.5">
            {(d.recommendations as string[]).map((r, i) => (
              <li key={i} className="text-xs text-foreground flex gap-1.5">
                <span className="text-emerald-700 flex-shrink-0">→</span> {r}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!!d.overall_conclusion && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Общий вывод</p>
          <p className="text-xs text-foreground leading-relaxed">{String(d.overall_conclusion)}</p>
        </div>
      )}
      {list && list.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
            Созданные блоки ({list.length})
          </p>
          <div className="space-y-0.5">
            {list.map((b, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px]">
                <span className="px-1 rounded text-[9px] font-medium bg-primary/10 text-primary border border-primary/20 flex-shrink-0">
                  {b.type ?? '?'}
                </span>
                <span className="text-muted-foreground truncate">{b.title ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {Array.isArray(d.series_used) && d.series_used.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Ряды данных</p>
          <div className="flex flex-wrap gap-1">
            {(d.series_used as string[]).map((s, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0 rounded bg-muted text-muted-foreground border">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const VerdictDetails: React.FC<{ d: Record<string, unknown>; approved: boolean }> = ({ d, approved }) => {
  const issues = d.issues as { severity?: string; category?: string; description?: string; suggested_fix?: string }[] | undefined
  const blocks = d.blocks as { type?: string; title?: string }[] | undefined
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs">
        <span>
          Оценка: <span className={cn('font-bold text-sm', approved ? 'text-emerald-800' : 'text-red-800')}>
            {typeof d.score === 'number' ? (d.score * 100).toFixed(0) + '%' : String(d.score)}
          </span>
        </span>
      </div>
      {!!d.reasoning && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Рассуждение критика</p>
          <p className="text-xs text-foreground leading-relaxed">{String(d.reasoning)}</p>
        </div>
      )}
      {blocks && blocks.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Одобренные блоки</p>
          <div className="space-y-0.5">
            {blocks.map((b, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px]">
                <span className="px-1 rounded text-[9px] font-medium bg-emerald-100 text-emerald-800 border border-emerald-300 flex-shrink-0">
                  {b.type ?? '?'}
                </span>
                <span className="text-muted-foreground truncate">{b.title ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {issues && issues.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
            Замечания критика ({issues.length})
          </p>
          <div className="space-y-2">
            {issues.map((issue, i) => (
              <div key={i} className="rounded border border-red-200 bg-red-50 px-2 py-1.5">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={cn(
                    'text-[9px] font-bold px-1 rounded',
                    issue.severity === 'CRITICAL' ? 'bg-red-700 text-white' :
                    issue.severity === 'MAJOR'    ? 'bg-orange-500 text-white' :
                                                   'bg-amber-400 text-amber-900',
                  )}>
                    {issue.severity}
                  </span>
                  {issue.category && (
                    <span className="text-[9px] text-muted-foreground">{issue.category}</span>
                  )}
                </div>
                <p className="text-[10px] text-foreground leading-snug">{issue.description}</p>
                {issue.suggested_fix && (
                  <p className="text-[10px] text-emerald-800 mt-0.5">→ {issue.suggested_fix}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const SessionCompleteDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => (
  <div className="space-y-2">
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
      {[
        ['Время', `${String(d.elapsed_s)}с`],
        ['Токенов', Number(d.total_tokens ?? 0).toLocaleString('ru')],
        ['Блоков', String(d.blocks_count ?? '—')],
        ['Качество', typeof d.quality_score === 'number' ? (d.quality_score * 100).toFixed(0) + '%' : '—'],
        ['Провайдер', String(d.llm_provider ?? '—')],
        ['Модель', String(d.model_name ?? '—')],
      ].map(([label, value]) => (
        <div key={label as string}>
          <span className="text-muted-foreground">{label as string}: </span>
          <span className="font-semibold text-foreground">{value as string}</span>
        </div>
      ))}
    </div>
    {!!d.departments_involved && (
      <div>
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Отделы</p>
        <div className="flex flex-wrap gap-1">
          {(d.departments_involved as string[]).map((dep, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0 rounded bg-muted text-muted-foreground border">
              {DEPT_LABELS[dep] ?? dep}
            </span>
          ))}
        </div>
      </div>
    )}
    {!!d.files_analyzed && (d.files_analyzed as string[]).length > 0 && (
      <div>
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Файлы</p>
        <div className="flex flex-wrap gap-1">
          {(d.files_analyzed as string[]).map((f, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0 rounded bg-muted text-foreground/70 border">{f}</span>
          ))}
        </div>
      </div>
    )}
  </div>
)

const TaskStartDetails: React.FC<{ d: Record<string, unknown> }> = ({ d }) => (
  <div className="space-y-1 text-xs">
    {!!d.description && (
      <div>
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-0.5">Описание задачи</p>
        <p className="text-foreground leading-relaxed">{String(d.description)}</p>
      </div>
    )}
    <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-muted-foreground">
      {d.max_retries !== undefined && <span>Макс. попыток: <span className="font-medium text-foreground">{String(d.max_retries as number)}</span></span>}
      {d.max_tokens !== undefined && <span>Макс. токенов: <span className="font-medium text-foreground">{Number(d.max_tokens as number).toLocaleString('ru')}</span></span>}
    </div>
    {Array.isArray(d.file_ids) && (d.file_ids as string[]).length > 0 && (
      <p className="text-[10px] text-muted-foreground">Файлов: {(d.file_ids as string[]).length}</p>
    )}
  </div>
)

function renderDetails(type: string, details: Record<string, unknown>) {
  switch (type) {
    case 'plan_created':     return <PlanDetails d={details} />
    case 'context_loaded':   return <ContextDetails d={details} />
    case 'tool_call':        return <ToolCallDetails d={details} />
    case 'nlp_analysis':     return <NLPDetails d={details} />
    case 'llm_response':     return <LLMResponseDetails d={details} />
    case 'verdict_approved': return <VerdictDetails d={details} approved={true} />
    case 'verdict_rejected': return <VerdictDetails d={details} approved={false} />
    case 'session_complete': return <SessionCompleteDetails d={details} />
    case 'task_start':       return <TaskStartDetails d={details} />
    default:
      return (
        <pre className="text-[10px] leading-relaxed bg-background rounded p-2 border overflow-x-auto text-muted-foreground max-h-64">
          {JSON.stringify(details, null, 2)}
        </pre>
      )
  }
}

// ── Single Event Row ─────────────────────────────────────────────────────────

const EventRow: React.FC<{ event: LogEvent; isLast: boolean }> = ({ event, isLast }) => {
  const meta = EVENT_META[event.type] ?? DEFAULT_META
  const Icon = meta.icon
  const hasDetail = event.details && Object.keys(event.details).length > 0
  const [open, setOpen] = useState(!!meta.autoExpand && !!hasDetail)

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
            {/* Header row */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className={cn('text-xs font-semibold', meta.color)}>{meta.label}</span>
              <span className="text-xs font-medium text-foreground/80">{event.agent}</span>

              {event.department && (
                <span className="text-[10px] px-1.5 py-0 rounded-full bg-muted text-muted-foreground border">
                  {DEPT_LABELS[event.department] ?? event.department}
                </span>
              )}

              {event.task_id && (
                <span className="text-[10px] font-mono px-1.5 py-0 rounded bg-primary/10 text-primary border border-primary/20"
                  title={event.task_id}>
                  #{shortId(event.task_id)}
                </span>
              )}

              <span className="ml-auto text-[10px] text-muted-foreground font-mono flex-shrink-0">
                {formatTime(event.ts)}
              </span>
            </div>

            {/* Message */}
            <p className="text-xs text-foreground/90 mt-0.5 leading-relaxed">{event.message}</p>

            {/* Expand toggle */}
            {hasDetail && (
              <button
                onClick={() => setOpen(o => !o)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground mt-1 transition-colors"
              >
                {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                {open ? 'Скрыть детали' : 'Показать детали'}
              </button>
            )}

            {/* Details panel */}
            {open && hasDetail && (
              <div className="mt-2 rounded border bg-background/70 px-3 py-2">
                {renderDetails(event.type, event.details!)}
              </div>
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

type FilterKey = 'all' | 'approved' | 'rejected' | 'errors' | 'blocks' | 'tools' | 'llm'

interface Props {
  events: LogEvent[]
  blackboardSnapshot?: Record<string, unknown>
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
      case 'tools':    return events.filter(e => e.type === 'tool_call' || e.type === 'nlp_analysis' || e.type === 'context_loaded')
      case 'llm':      return events.filter(e => e.type === 'llm_response')
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
        <Database className="h-10 w-10 text-muted-foreground/40 mb-3" />
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
            ['tools',    'Инструменты'],
            ['llm',      'LLM'],
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
              ? 'bg-emerald-100 text-emerald-900 border-emerald-500 dark:bg-emerald-950/50'
              : 'bg-muted text-muted-foreground hover:text-foreground hover:border-border',
          )}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Скопировано' : 'Копировать JSON'}
        </button>
      </div>

      {/* Stats strip */}
      <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground px-1">
        <span>
          <span className="text-emerald-800 font-semibold">
            {events.filter(e => e.type === 'verdict_approved').length}
          </span> одобрено
        </span>
        <span>
          <span className="text-rose-800 font-semibold">
            {events.filter(e => e.type === 'verdict_rejected').length}
          </span> отклонено
        </span>
        <span>
          <span className="text-teal-800 font-semibold">
            {events.filter(e => e.type === 'block_published').length}
          </span> блоков
        </span>
        <span>
          <span className="text-teal-800 font-semibold">
            {events.filter(e => e.type === 'tool_call' || e.type === 'nlp_analysis').length}
          </span> вызовов инструментов
        </span>
        <span>
          <span className="text-blue-800 font-semibold">
            {events.filter(e => e.type === 'llm_response').length}
          </span> LLM-ответов
        </span>
        {events.filter(e => e.type === 'task_error').length > 0 && (
          <span>
            <span className="text-red-800 font-semibold">
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
