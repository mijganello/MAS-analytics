import React from 'react'
import { AlertTriangle } from 'lucide-react'
import type { ReportBlock } from '@/types/blocks'
import { TextBlockComponent } from './TextBlock'
import { KPICardComponent } from './KPICard'
import { TableBlockComponent } from './TableBlock'
import { ChartBlockComponent } from './ChartBlock'
import { InsightBlockComponent } from './InsightBlock'
import { ComparisonBlockComponent } from './ComparisonBlock'
import { ForecastBlockComponent } from './ForecastBlock'
import { RiskMatrixBlockComponent } from './RiskMatrix'
import { ExecutiveSummaryComponent } from './ExecutiveSummary'

interface Props {
  block: ReportBlock
}

export const BlockRenderer: React.FC<Props> = ({ block }) => {
  const renderBlock = () => {
    switch (block.block_type) {
      case 'text': return <TextBlockComponent {...block} />
      case 'kpi_card': return <KPICardComponent {...block} />
      case 'table': return <TableBlockComponent {...block} />
      case 'chart': return <ChartBlockComponent {...block} />
      case 'insight': return <InsightBlockComponent {...block} />
      case 'comparison': return <ComparisonBlockComponent {...block} />
      case 'forecast': return <ForecastBlockComponent {...block} />
      case 'risk_matrix': return <RiskMatrixBlockComponent {...block} />
      case 'executive_summary': return <ExecutiveSummaryComponent {...block} />
      default:
        return (
          <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            Неизвестный тип блока: {(block as ReportBlock).block_type}
          </div>
        )
    }
  }

  return (
    <div className="relative" id={`block-${block.block_id}`}>
      {block.status === 'partial' && (
        <div className="flex items-center gap-1.5 text-xs text-amber-600 mb-2">
          <AlertTriangle className="h-3 w-3" />
          <span>Частичные данные: {block.warnings.join('; ')}</span>
        </div>
      )}
      {renderBlock()}
    </div>
  )
}
