import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { QueryForm } from '@/features/query-input/QueryForm'
import { ReportCanvas } from '@/features/report-builder/ReportCanvas'
import { AgentLog } from '@/components/AgentLog'
import { ReportsSidebar } from '@/components/ReportsSidebar'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useReportStream } from '@/hooks/useReportStream'
import { useStore } from '@/app/store'
import { api } from '@/lib/api'
import { BarChart3, BookOpen, ScrollText, Copy, Check } from 'lucide-react'

export const Home: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'report' | 'log'>('report')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [copied, setCopied] = useState(false)
  const { blocks, isGenerating, logEvents, resetBlocks, resetLog, resetTasks } = useStore()
  const contentRef = useRef<HTMLDivElement>(null)

  useReportStream(sessionId)

  const handleSessionCreated = (id: string) => {
    setSessionId(id)
    setActiveTab('report')
  }

  const handleNewChat = useCallback(() => {
    resetBlocks()
    resetLog()
    resetTasks()
    setSessionId(null)
  }, [resetBlocks, resetLog, resetTasks])

  const hasContent = blocks.length > 0 || isGenerating

  useEffect(() => {
    if (isGenerating && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [blocks.length, isGenerating])

  const copyReportJson = async () => {
    let json: object
    if (sessionId) {
      try {
        json = await api.getReport(sessionId)
      } catch {
        json = { session_id: sessionId, blocks, log_events: logEvents }
      }
    } else {
      json = { blocks, log_events: logEvents }
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(json, null, 2))
    } catch {
      const ta = document.createElement('textarea')
      ta.value = JSON.stringify(json, null, 2)
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">

      {/* ── Full-width header ── */}
      <header className="shrink-0 border-b bg-muted/80 backdrop-blur z-20">
        <div className="px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <BarChart3 className="h-5 w-5 text-primary" />
            <span className="font-semibold text-foreground">MAS Analytics</span>
            <span className="text-xs text-muted-foreground hidden md:inline">· Многоагентная аналитика</span>
          </div>
          <div className="flex items-center gap-3">
            {isGenerating && (
              <span className="flex items-center gap-1.5 text-xs text-primary">
                <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                Генерация
              </span>
            )}
            <Link
              to="/reports"
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Все отчёты</span>
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* ── Main body: sidebar + content ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <ReportsSidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(v => !v)}
          onNewChat={handleNewChat}
          currentSessionId={sessionId}
        />

        {/* Right: scrollable content + fixed input */}
        <div className="flex flex-col flex-1 overflow-hidden">

          {/* Scrollable content */}
          <div ref={contentRef} className="flex-1 overflow-y-auto">
            <div className="max-w-5xl mx-auto px-6 py-6 pb-4">
              {!hasContent ? (
                /* Empty state */
                <div className="flex flex-col items-center justify-center min-h-[55vh] text-center space-y-6 py-10">
                  <div className="rounded-2xl bg-primary/10 p-5">
                    <BarChart3 className="h-10 w-10 text-primary" />
                  </div>
                  <div className="space-y-2">
                    <h1 className="text-2xl font-bold text-foreground">Аналитика под управлением агентов</h1>
                    <p className="text-muted-foreground max-w-md text-sm leading-relaxed">
                      Загрузите файл и опишите задачу — агенты автоматически извлекут данные,
                      верифицируют их и сгенерируют структурированный отчёт.
                    </p>
                  </div>
                </div>
              ) : (
                /* Content with tabs */
                <div className="space-y-4">
                  {/* Tab bar */}
                  <div className="flex items-center gap-0.5 border-b">
                    {([
                      { key: 'report' as const, icon: BarChart3,   label: 'Отчёт',       count: blocks.length },
                      { key: 'log'    as const, icon: ScrollText,  label: 'Лог агентов', count: logEvents.length },
                    ]).map(({ key, icon: Icon, label, count }) => (
                      <button
                        key={key}
                        onClick={() => setActiveTab(key)}
                        className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                          activeTab === key
                            ? 'border-primary text-foreground'
                            : 'border-transparent text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        {label}
                        {count > 0 && (
                          <span className={`ml-1 text-xs px-1.5 rounded-full ${
                            activeTab === key
                              ? 'bg-primary/10 text-primary'
                              : 'bg-muted text-muted-foreground'
                          }`}>
                            {count}
                          </span>
                        )}
                      </button>
                    ))}
                    {/* Copy JSON button — right-aligned */}
                    {hasContent && (
                      <button
                        onClick={copyReportJson}
                        className="ml-auto flex items-center gap-1.5 px-3 py-2 text-xs font-medium
                                   text-muted-foreground hover:text-foreground transition-colors"
                        title="Скопировать отчёт как JSON"
                      >
                        {copied ? (
                          <>
                            <Check className="h-3.5 w-3.5 text-green-600" />
                            <span className="text-green-600">Скопировано</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            <span>JSON</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {activeTab === 'report' ? (
                    <ReportCanvas />
                  ) : (
                    <div className="rounded-2xl border bg-card p-5 shadow-sm">
                      <AgentLog events={logEvents} autoScroll />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── Fixed chat input ── */}
          <div className="shrink-0 border-t bg-muted/80 backdrop-blur">
            <div className="max-w-5xl mx-auto px-6 py-3">
              <QueryForm onSessionCreated={handleSessionCreated} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
