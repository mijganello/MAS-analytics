import React from 'react'
import { BlockRenderer } from '@/components/blocks/BlockRenderer'
import { BlockErrorBoundary } from '@/components/BlockErrorBoundary'
import { useStore } from '@/app/store'
import type { ReportBlock } from '@/types/blocks'

// Group consecutive kpi_card blocks together; all other blocks stay solo.
type BlockGroup =
  | { kind: 'kpi_grid'; blocks: ReportBlock[] }
  | { kind: 'single'; block: ReportBlock }

function groupBlocks(blocks: ReportBlock[]): BlockGroup[] {
  const groups: BlockGroup[] = []
  let i = 0
  while (i < blocks.length) {
    if (blocks[i].block_type === 'kpi_card') {
      const run: ReportBlock[] = []
      while (i < blocks.length && blocks[i].block_type === 'kpi_card') {
        run.push(blocks[i++])
      }
      groups.push({ kind: 'kpi_grid', blocks: run })
    } else {
      groups.push({ kind: 'single', block: blocks[i++] })
    }
  }
  return groups
}

function gridCols(count: number): string {
  if (count === 1) return 'grid-cols-1'
  if (count === 2) return 'grid-cols-2'
  if (count === 3) return 'grid-cols-3'
  return 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4'
}

export const ReportCanvas: React.FC = () => {
  const { blocks, isGenerating } = useStore()

  if (blocks.length === 0 && !isGenerating) return null

  const groups = groupBlocks(blocks)

  return (
    <div className="space-y-6">
      {groups.map((group, gi) =>
        group.kind === 'kpi_grid' ? (
          <div
            key={`grid-${gi}`}
            className={`grid gap-4 ${gridCols(group.blocks.length)} animate-in fade-in slide-in-from-bottom-2 duration-300`}
          >
            {group.blocks.map(block => (
              <BlockErrorBoundary key={block.block_id}>
                <BlockRenderer block={block} />
              </BlockErrorBoundary>
            ))}
          </div>
        ) : (
          <div
            key={group.block.block_id}
            className="animate-in fade-in slide-in-from-bottom-2 duration-300"
          >
            <BlockErrorBoundary>
              <BlockRenderer block={group.block} />
            </BlockErrorBoundary>
          </div>
        )
      )}

      {isGenerating && (
        <div className="flex items-center gap-3 rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          <span className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full flex-shrink-0" />
          <span>Агенты работают над следующим блоком...</span>
        </div>
      )}
    </div>
  )
}
