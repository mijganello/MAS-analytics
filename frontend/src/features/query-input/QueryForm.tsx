import React, { useCallback, useRef, useState, useEffect } from 'react'
import { Paperclip, X, FileText, FileSpreadsheet, Braces, File, ArrowUp } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/app/store'
import { cn, formatBytes } from '@/lib/utils'
import type { UploadedFile } from '@/types/blocks'

interface Props {
  onSessionCreated: (sessionId: string) => void
}

const FILE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  pdf: FileText,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  csv: FileSpreadsheet,
  docx: FileText,
  txt: FileText,
  json: Braces,
}

/* ── iOS-style segmented control ── */
const ModelSwitch: React.FC<{
  value: 'deepseek' | 'ollama'
  onChange: (v: 'deepseek' | 'ollama') => void
}> = ({ value, onChange }) => {
  const options: { id: 'deepseek' | 'ollama'; label: string; sub: string }[] = [
    { id: 'deepseek', label: 'DeepSeek', sub: 'API' },
    { id: 'ollama',   label: 'Ollama',   sub: 'Local' },
  ]

  return (
    <div className="inline-flex items-center rounded-full bg-muted p-0.5 gap-0.5">
      {options.map(opt => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onChange(opt.id)}
          className={cn(
            'relative flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-all duration-200',
            value === opt.id
              ? 'bg-card text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {opt.label}
          <span className={cn(
            'text-[10px] font-normal transition-colors',
            value === opt.id ? 'text-primary' : 'text-muted-foreground/60',
          )}>
            {opt.sub}
          </span>
        </button>
      ))}
    </div>
  )
}

/* ── File chip ── */
const FileChip: React.FC<{ file: UploadedFile; onRemove: () => void }> = ({ file, onRemove }) => {
  const ext = file.filename.split('.').pop()?.toLowerCase() ?? ''
  const Icon = FILE_ICONS[ext] ?? File

  return (
    <div className="flex items-center gap-1.5 rounded-full bg-muted border px-2.5 py-1 text-xs max-w-[160px]">
      <Icon className="h-3 w-3 text-muted-foreground shrink-0" />
      <span className="truncate text-foreground font-medium">{file.filename}</span>
      <span className="text-muted-foreground shrink-0">{formatBytes(file.size_bytes)}</span>
      {file.status === 'processing' ? (
        <span className="h-2 w-2 rounded-full border border-primary border-t-transparent animate-spin shrink-0" />
      ) : (
        <button
          type="button"
          onClick={onRemove}
          className="shrink-0 text-muted-foreground hover:text-destructive transition-colors"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  )
}

/* ── Main component ── */
export const QueryForm: React.FC<Props> = ({ onSessionCreated }) => {
  const { uploadedFiles, addFile, removeFile, provider, setProvider, resetBlocks, resetLog } = useStore()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const canSubmit = query.trim().length >= 5 && uploadedFiles.length > 0 && !loading && !uploading

  /* Auto-resize textarea */
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }, [query])

  /* Handle keyboard: Cmd/Ctrl+Enter submits */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (canSubmit) handleSubmit(e as unknown as React.FormEvent)
    }
  }

  /* File upload */
  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      const results = await api.uploadFiles(Array.from(files))
      // Mark as 'done' immediately — upload completed successfully, file is ready for use
      results.forEach(f => addFile({ ...f, status: 'done' }))
    } catch (e) {
      setError(`Ошибка загрузки: ${e}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [addFile])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  /* Submit */
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
    <form onSubmit={handleSubmit} className="space-y-2">

      {/* File chips row */}
      {uploadedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {uploadedFiles.map(f => (
            <FileChip key={f.file_id} file={f} onRemove={() => removeFile(f.file_id)} />
          ))}
        </div>
      )}

      {/* Input box */}
      <div
        className={cn(
          'relative rounded-2xl border bg-card transition-shadow',
          'focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/60',
        )}
        onDragOver={e => e.preventDefault()}
        onDrop={onDrop}
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.xlsx,.xls,.csv,.docx,.txt,.json"
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Опишите аналитическую задачу..."
          rows={1}
          className={cn(
            'w-full resize-none bg-transparent px-4 py-3 pr-20 text-sm',
            'placeholder:text-muted-foreground focus:outline-none',
            'min-h-[44px] max-h-[200px]',
          )}
        />

        {/* Action buttons inside the box */}
        <div className="absolute right-2 bottom-2 flex items-center gap-1">
          {/* Attach file */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className={cn(
              'h-8 w-8 rounded-xl flex items-center justify-center transition-colors',
              uploading
                ? 'text-primary'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted',
            )}
            title="Прикрепить файл"
          >
            {uploading ? (
              <span className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            ) : (
              <Paperclip className="h-4 w-4" />
            )}
          </button>

          {/* Send */}
          <button
            type="submit"
            disabled={!canSubmit}
            className={cn(
              'h-8 w-8 rounded-xl flex items-center justify-center transition-all',
              canSubmit
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50',
            )}
            title="Сгенерировать отчёт (Ctrl+Enter)"
          >
            {loading ? (
              <span className="h-4 w-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Footer: model switch + hint */}
      <div className="flex items-center justify-between px-0.5">
        <ModelSwitch value={provider} onChange={setProvider} />
        <span className="text-[11px] text-muted-foreground/60 hidden sm:block">
          {canSubmit ? 'Ctrl+Enter — отправить' : uploadedFiles.length === 0 ? 'Прикрепите файл' : 'Введите запрос'}
        </span>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-destructive px-1">{error}</p>
      )}
    </form>
  )
}
