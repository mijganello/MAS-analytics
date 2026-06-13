import React, { useState } from 'react'
import { Send, Bot } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/app/store'
import { cn } from '@/lib/utils'

interface Props {
  onSessionCreated: (sessionId: string) => void
}

export const QueryForm: React.FC<Props> = ({ onSessionCreated }) => {
  const { uploadedFiles, provider, setProvider, resetBlocks, resetLog } = useStore()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canSubmit = query.trim().length >= 5 && uploadedFiles.length > 0 && !loading

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError('')
    resetBlocks()
    resetLog()
    try {
      const { session_id } = await api.createSession(
        query.trim(),
        uploadedFiles.map(f => f.file_id),
        provider,
      )
      onSessionCreated(session_id)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">Запрос к данным</label>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Проанализируй динамику продаж за последние 3 периода, выяви тренды и аномалии..."
          rows={4}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary placeholder:text-muted-foreground"
        />
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">Модель:</span>
        {(['deepseek', 'ollama'] as const).map(p => (
          <button
            key={p}
            type="button"
            onClick={() => setProvider(p)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              provider === p
                ? 'bg-primary text-primary-foreground'
                : 'border text-muted-foreground hover:border-primary hover:text-foreground'
            )}
          >
            <Bot className="h-3 w-3" />
            {p === 'deepseek' ? 'DeepSeek API' : 'LLaMA (локально)'}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <span className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full" />
            Создаю отчёт...
          </span>
        ) : (
          <>
            <Send className="h-4 w-4" />
            Сгенерировать отчёт
          </>
        )}
      </button>
    </form>
  )
}
