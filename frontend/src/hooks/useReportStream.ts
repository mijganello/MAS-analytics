import { useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import { useStore } from '@/app/store'
import type { ReportBlock, TaskStatusEvent } from '@/types/blocks'
import type { LogEvent } from '@/app/store'

export function useReportStream(sessionId: string | null) {
  const { addBlock, upsertTask, setGenerating, appendLogEvent } = useStore()
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!sessionId) return

    setGenerating(true)
    const es = api.streamReport(sessionId)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (event.type === 'block_approved' && event.block_type) {
          addBlock(event as ReportBlock)
        } else if (event.type === 'task_status') {
          upsertTask(event as TaskStatusEvent)
        } else if (event.type === 'agent_log') {
          appendLogEvent({
            ts: event.ts,
            type: event.event_type,
            agent: event.agent,
            message: event.message,
            task_id: event.task_id,
            department: event.department,
            details: event.details,
          } as LogEvent)
        } else if (event.type === 'session_done') {
          setGenerating(false)
          es.close()
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      setGenerating(false)
      es.close()
    }

    return () => {
      es.close()
      setGenerating(false)
    }
  }, [sessionId])

  return { stop: () => esRef.current?.close() }
}
