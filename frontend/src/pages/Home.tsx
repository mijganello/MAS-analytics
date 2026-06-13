import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileUploadZone } from '@/features/file-upload/FileUploadZone'
import { QueryForm } from '@/features/query-input/QueryForm'
import { ReportCanvas } from '@/features/report-builder/ReportCanvas'
import { AgentMonitor } from '@/features/agent-monitor/AgentMonitor'
import { AgentLog } from '@/components/AgentLog'
import { useReportStream } from '@/hooks/useReportStream'
import { useStore } from '@/app/store'
import { BarChart3, BookOpen, ScrollText } from 'lucide-react'

export const Home: React.FC = () => {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'report' | 'log'>('report')
  const { blocks, isGenerating, logEvents } = useStore()

  useReportStream(sessionId)

  const handleSessionCreated = (id: string) => {
    setSessionId(id)
  }

  const hasReport = blocks.length > 0 || isGenerating

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-primary" />
            <span className="font-bold text-foreground">MAS Analytics</span>
            <span className="text-xs text-muted-foreground hidden sm:block">/ Многоагентная аналитика</span>
          </div>
          <div className="flex items-center gap-3">
            {isGenerating && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="animate-spin h-3 w-3 border-2 border-primary border-t-transparent rounded-full" />
                Генерация...
              </span>
            )}
            <Link
              to="/reports"
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              <span className="hidden sm:inline">Отчёты</span>
            </Link>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6">
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          {/* Left panel */}
          <aside className="space-y-6">
            <div className="rounded-xl border bg-card p-5 space-y-5 shadow-sm">
              <div>
                <h2 className="font-semibold text-foreground text-sm mb-1">Данные для анализа</h2>
                <p className="text-xs text-muted-foreground">Загрузите файлы — агенты извлекут и верифицируют данные автоматически</p>
              </div>
              <FileUploadZone />
            </div>

            <div className="rounded-xl border bg-card p-5 shadow-sm">
              <QueryForm onSessionCreated={handleSessionCreated} />
            </div>

            {hasReport && (
              <div className="rounded-xl border bg-card p-5 shadow-sm">
                <AgentMonitor />
              </div>
            )}
          </aside>

          {/* Main content */}
          <main>
            {!hasReport ? (
              <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4">
                <div className="rounded-full bg-primary/10 p-6">
                  <BarChart3 className="h-12 w-12 text-primary" />
                </div>
                <h1 className="text-2xl font-bold text-foreground">Аналитика под управлением агентов</h1>
                <p className="text-muted-foreground max-w-md text-sm leading-relaxed">
                  Загрузите файлы и опишите задачу. Система многоагентного анализа автоматически
                  декомпозирует запрос, извлечёт данные, проверит их через цифровой слепок
                  и сгенерирует структурированный отчёт.
                </p>
                <div className="grid grid-cols-3 gap-3 mt-4 text-xs text-muted-foreground max-w-sm">
                  {['PDF / XLSX / CSV', 'Верификация чисел', 'Структурированный отчёт'].map(t => (
                    <div key={t} className="rounded-lg border p-3 text-center bg-muted/30">{t}</div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Tab bar */}
                <div className="flex items-center gap-1 border-b">
                  <button
                    onClick={() => setActiveTab('report')}
                    className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'report'
                        ? 'border-primary text-foreground'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <BarChart3 className="h-3.5 w-3.5" />
                    Отчёт
                    {blocks.length > 0 && (
                      <span className="ml-1 text-xs bg-primary/10 text-primary px-1.5 rounded-full">
                        {blocks.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setActiveTab('log')}
                    className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'log'
                        ? 'border-primary text-foreground'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <ScrollText className="h-3.5 w-3.5" />
                    Лог агентов
                    {logEvents.length > 0 && (
                      <span className="ml-1 text-xs bg-muted text-muted-foreground px-1.5 rounded-full">
                        {logEvents.length}
                      </span>
                    )}
                  </button>
                </div>

                {activeTab === 'report' ? (
                  <ReportCanvas />
                ) : (
                  <div className="rounded-xl border bg-card p-5 shadow-sm">
                    <AgentLog events={logEvents} autoScroll />
                  </div>
                )}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}
