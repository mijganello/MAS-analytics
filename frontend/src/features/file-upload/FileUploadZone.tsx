import React, { useCallback, useState } from 'react'
import { Upload, X, FileText, FileSpreadsheet, File, Braces } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/app/store'
import { formatBytes, cn } from '@/lib/utils'

const fileIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  pdf: FileText,
  xlsx: FileSpreadsheet,
  csv: FileSpreadsheet,
  docx: FileText,
  txt: FileText,
  json: Braces,
}

export const FileUploadZone: React.FC = () => {
  const { uploadedFiles, addFile, removeFile } = useStore()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      const results = await api.uploadFiles(Array.from(files))
      results.forEach(f => addFile(f))
    } catch (e) {
      console.error('Upload error:', e)
    } finally {
      setUploading(false)
    }
  }, [addFile])

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all',
          dragging ? 'border-primary bg-primary/5 scale-[1.01]' : 'border-muted-foreground/30 hover:border-primary/50 hover:bg-muted/30'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.xlsx,.xls,.csv,.docx,.txt,.json"
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />
        <Upload className={cn('mx-auto h-10 w-10 mb-3', dragging ? 'text-primary' : 'text-muted-foreground')} />
        <p className="text-sm font-medium text-foreground">
          {uploading ? 'Загрузка...' : 'Перетащите файлы или нажмите для выбора'}
        </p>
        <p className="text-xs text-muted-foreground mt-1">PDF, XLSX, CSV, DOCX, TXT, JSON · до 50 МБ</p>
      </div>

      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          {uploadedFiles.map(f => {
            const Icon = fileIcons[f.file_type] || File
            return (
              <div key={f.file_id} className="flex items-center gap-3 rounded-lg border px-3 py-2 text-sm">
                <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="truncate font-medium text-foreground">{f.filename}</p>
                  <p className="text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</p>
                </div>
                <span className={cn(
                  'text-xs px-2 py-0.5 rounded-full',
                  f.status === 'done' ? 'bg-emerald-100 text-emerald-700' : 'bg-muted text-muted-foreground'
                )}>
                  {f.status === 'processing' ? '⏳' : '✓'}
                </span>
                <button onClick={() => removeFile(f.file_id)} className="text-muted-foreground hover:text-destructive transition-colors">
                  <X className="h-4 w-4" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
