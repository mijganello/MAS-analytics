import { create } from 'zustand'
import type { ReportBlock, TaskStatusEvent, UploadedFile } from '@/types/blocks'

export interface LogEvent {
  ts: string
  type: string
  agent: string
  message: string
  task_id?: string | null
  department?: string | null
  details?: Record<string, unknown>
}

interface AppState {
  // Files
  uploadedFiles: UploadedFile[]
  setUploadedFiles: (files: UploadedFile[]) => void
  addFile: (f: UploadedFile) => void
  removeFile: (id: string) => void

  // Session
  sessionId: string | null
  setSessionId: (id: string | null) => void

  // Report streaming
  blocks: ReportBlock[]
  addBlock: (b: ReportBlock) => void
  resetBlocks: () => void

  // Task statuses
  taskStatuses: TaskStatusEvent[]
  upsertTask: (t: TaskStatusEvent) => void

  // Agent log (live, from SSE)
  logEvents: LogEvent[]
  appendLogEvent: (e: LogEvent) => void
  resetLog: () => void

  // UI
  isGenerating: boolean
  setGenerating: (v: boolean) => void
  provider: 'deepseek' | 'ollama'
  setProvider: (p: 'deepseek' | 'ollama') => void
}

export const useStore = create<AppState>((set) => ({
  uploadedFiles: [],
  setUploadedFiles: (files) => set({ uploadedFiles: files }),
  addFile: (f) => set((s) => ({ uploadedFiles: [...s.uploadedFiles, f] })),
  removeFile: (id) => set((s) => ({ uploadedFiles: s.uploadedFiles.filter(f => f.file_id !== id) })),

  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),

  blocks: [],
  addBlock: (b) => set((s) => {
    const existing = s.blocks.find(x => x.block_id === b.block_id)
    if (existing) return s
    const next = [...s.blocks, b].sort((a, c) => a.order - c.order)
    return { blocks: next }
  }),
  resetBlocks: () => set({ blocks: [] }),

  taskStatuses: [],
  upsertTask: (t) => set((s) => {
    const existing = s.taskStatuses.findIndex(x => x.task_id === t.task_id)
    if (existing >= 0) {
      const copy = [...s.taskStatuses]
      copy[existing] = t
      return { taskStatuses: copy }
    }
    return { taskStatuses: [...s.taskStatuses, t] }
  }),

  logEvents: [],
  appendLogEvent: (e) => set((s) => ({ logEvents: [...s.logEvents, e] })),
  resetLog: () => set({ logEvents: [] }),

  isGenerating: false,
  setGenerating: (v) => set({ isGenerating: v }),

  provider: 'deepseek',
  setProvider: (p) => set({ provider: p }),
}))
