import React from 'react'
import type { ForecastBlock } from '@/types/blocks'
import { ChartBlockComponent } from './ChartBlock'
import { formatNumber } from '@/lib/utils'

export const ForecastBlockComponent: React.FC<ForecastBlock> = ({
  title, metric_name, historical, forecast, method, model_accuracy
}) => {
  const safeHistorical = Array.isArray(historical) ? historical : []
  const safeForecast = Array.isArray(forecast) ? forecast : []
  const safeAccuracy = model_accuracy && typeof model_accuracy === 'object' ? model_accuracy : {}
  const safeMethod = method ?? 'Н/Д'
  const safeTitle = title || metric_name || 'Прогноз'

  const histData = safeHistorical.map(p => ({
    period: p?.period ?? '', value: p?.value ?? 0, type: 'Исторические данные'
  }))
  const forecastData = safeForecast.map(p => ({
    period: p?.period ?? '', value: p?.value ?? 0,
    lower: p?.lower_bound ?? 0, upper: p?.upper_bound ?? 0,
    type: 'Прогноз'
  }))

  const allPoints = [
    ...histData,
    ...forecastData.map(d => ({ period: d.period, value: d.value, type: d.type })),
  ]

  const spec = {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: safeTitle,
    layer: [
      {
        data: { values: allPoints },
        mark: { type: 'line', strokeWidth: 2 },
        encoding: {
          x: { field: 'period', type: 'ordinal', title: 'Период' },
          y: { field: 'value', type: 'quantitative', title: metric_name ?? 'Значение' },
          color: {
            field: 'type', type: 'nominal',
            scale: { domain: ['Исторические данные', 'Прогноз'], range: ['#003C8A', '#D45800'] },
            title: 'Тип',
          },
          tooltip: [{ field: 'period', title: 'Период' }, { field: 'value', format: ',.2f', title: 'Значение' }],
        },
      },
      ...(forecastData.length > 0 ? [{
        data: { values: forecastData },
        mark: { type: 'area', opacity: 0.25, color: '#D45800' },
        encoding: {
          x: { field: 'period', type: 'ordinal' },
          y: { field: 'lower', type: 'quantitative' },
          y2: { field: 'upper' },
        },
      }] : []),
    ],
    width: 'container' as const,
    height: 280,
  }

  return (
    <div className="space-y-3">
      <ChartBlockComponent
        block_id="" block_type="chart" title={safeTitle} order={0}
        status="complete" warnings={[]} source_task_ids={[]} created_by_dept=""
        created_at="" chart_type="line" vega_lite_spec={spec}
        data_source_description={safeMethod} interactive={true}
      />
      <div className="flex gap-4 text-xs text-muted-foreground flex-wrap">
        <span>Метод: {safeMethod}</span>
        {safeAccuracy.MAE !== undefined && (
          <span>MAE: {formatNumber(safeAccuracy.MAE as number, 3)}</span>
        )}
        {safeAccuracy.MAPE_pct !== undefined && (
          <span>MAPE: {formatNumber(safeAccuracy.MAPE_pct as number, 1)}%</span>
        )}
        {safeAccuracy.RMSE !== undefined && (
          <span>RMSE: {formatNumber(safeAccuracy.RMSE as number, 3)}</span>
        )}
      </div>
    </div>
  )
}
