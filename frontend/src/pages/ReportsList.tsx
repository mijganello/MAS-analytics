import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { BarChart3, ArrowLeft, FileText, Calendar, Cpu, ChevronRight, AlertCircle } from 'lucide-react'

export const ReportsList: React.FC = () => {
  const { data: reports, isLoading, error } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.listReports(),
  })

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card/50 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="h-4 w-4" />
              <span>Назад</span>
            </Link>
            <span className="text-muted-foreground">/</span>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              <span className="font-semibold text-foreground">Сгенерированные отчёты</span>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {isLoading && (
          <div className="flex items-center justify-center py-16 text-muted-foreground gap-3">
            <span className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
            <span>Загрузка отчётов...</span>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center gap-3 text-red-700">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span className="text-sm">Не удалось загрузить список отчётов</span>
          </div>
        )}

        {reports && reports.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center space-y-3">
            <div className="rounded-full bg-muted p-5">
              <FileText className="h-10 w-10 text-muted-foreground" />
            </div>
            <p className="text-lg font-medium text-foreground">Отчётов пока нет</p>
            <p className="text-sm text-muted-foreground">Сгенерируйте первый отчёт на главной странице</p>
            <Link
              to="/"
              className="mt-2 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Создать отчёт
            </Link>
          </div>
        )}

        {reports && reports.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground mb-4">
              Найдено отчётов: <span className="font-medium text-foreground">{reports.length}</span>
            </p>
            {reports.map(report => (
              <Link
                key={report.report_id}
                to={`/reports/${report.report_id}`}
                className="block rounded-xl border bg-card p-5 hover:border-primary/50 hover:shadow-sm transition-all group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-foreground truncate group-hover:text-primary transition-colors">
                      {report.title}
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                      {report.query}
                    </p>
                    <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground flex-wrap">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(report.created_at)}
                      </span>
                      {report.llm_provider && (
                        <span className="flex items-center gap-1">
                          <Cpu className="h-3 w-3" />
                          {report.llm_provider}
                        </span>
                      )}
                      {report.total_tokens > 0 && (
                        <span>{report.total_tokens.toLocaleString()} токенов</span>
                      )}
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                        report.status === 'complete'
                          ? 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400'
                          : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400'
                      }`}>
                        {report.status === 'complete' ? 'Готов' : 'Ошибка'}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors flex-shrink-0 mt-0.5" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
