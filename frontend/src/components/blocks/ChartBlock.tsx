import React, { useMemo } from 'react'
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  PieChart, Pie, Cell,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'
import type { ChartBlock } from '@/types/blocks'
import { cn } from '@/lib/utils'

// ── Colour palette ────────────────────────────────────────────────────────────
const PALETTE = [
  '#6366f1', // indigo-500
  '#22c55e', // green-500
  '#f59e0b', // amber-500
  '#ef4444', // red-500
  '#3b82f6', // blue-500
  '#a855f7', // purple-500
  '#14b8a6', // teal-500
  '#f97316', // orange-500
]

// ── Vega-Lite spec parser ─────────────────────────────────────────────────────

interface ParsedChart {
  type: 'bar' | 'line' | 'area' | 'pie' | 'scatter'
  data: Record<string, unknown>[]
  xField: string
  yField: string
  colorField?: string
  series: string[]       // unique series values (for multi-series)
  title?: string
  xLabel?: string
  yLabel?: string
}

function parseVegaLite(spec: Record<string, unknown>): ParsedChart | null {
  try {
    // Extract mark type
    const rawMark = typeof spec.mark === 'string' ? spec.mark
      : typeof spec.mark === 'object' && spec.mark !== null ? (spec.mark as Record<string, unknown>).type as string
      : 'bar'

    const markMap: Record<string, ParsedChart['type']> = {
      bar: 'bar', rect: 'bar',
      line: 'line', rule: 'line',
      area: 'area',
      arc: 'pie', pie: 'pie',
      point: 'scatter', circle: 'scatter',
    }
    const type = markMap[rawMark] ?? 'bar'

    // Extract data
    const dataObj = spec.data as Record<string, unknown> | undefined
    let rawData: Record<string, unknown>[] = []
    if (Array.isArray(dataObj?.values)) {
      rawData = dataObj.values as Record<string, unknown>[]
    } else if (Array.isArray(spec.values)) {
      rawData = spec.values as Record<string, unknown>[]
    }
    if (rawData.length === 0) return null

    // Extract encoding
    const enc = (spec.encoding ?? {}) as Record<string, Record<string, unknown>>
    const xField = (enc.x?.field ?? enc.theta?.field ?? Object.keys(rawData[0])[0]) as string
    const yField = (enc.y?.field ?? enc.radius?.field ?? Object.keys(rawData[0])[1] ?? xField) as string
    const colorField = enc.color?.field as string | undefined

    const xAxisEnc = enc.x as Record<string, unknown> | undefined
    const yAxisEnc = enc.y as Record<string, unknown> | undefined
    const xLabel = (xAxisEnc?.['title'] ?? (xAxisEnc?.['axis'] as Record<string, unknown>)?.['title'] ?? xField) as string | undefined
    const yLabel = (yAxisEnc?.['title'] ?? (yAxisEnc?.['axis'] as Record<string, unknown>)?.['title'] ?? yField) as string | undefined

    // Determine series for multi-line/bar
    const series: string[] = colorField
      ? [...new Set(rawData.map(d => String(d[colorField] ?? '')))]
      : [yField]

    return { type, data: rawData, xField, yField, colorField, series, xLabel, yLabel, title: spec.title as string | undefined }
  } catch {
    return null
  }
}

// ── Tooltip styles ────────────────────────────────────────────────────────────

const CustomTooltip = ({
  active, payload, label,
}: {
  active?: boolean
  payload?: { name: string; value: unknown; color: string }[]
  label?: string
}) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-card shadow-lg px-3 py-2 text-xs space-y-1">
      {label && <p className="font-semibold text-foreground mb-1">{label}</p>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium text-foreground">{formatVal(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

function formatVal(v: unknown): string {
  if (typeof v === 'number') {
    if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M'
    if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(1) + 'k'
    return v % 1 === 0 ? String(v) : v.toFixed(2)
  }
  return String(v ?? '')
}

const axisStyle = { fontSize: 11, fill: '#94a3b8' }

// ── Chart renderers ───────────────────────────────────────────────────────────

const BarChartRenderer: React.FC<{ parsed: ParsedChart }> = ({ parsed }) => {
  const { data, xField, yField, colorField, series } = parsed

  // multi-series or single
  if (colorField && series.length > 1) {
    // Pivot data: group by xField, one key per series value
    const pivoted = Object.values(
      data.reduce<Record<string, Record<string, unknown>>>((acc, row) => {
        const key = String(row[xField])
        if (!acc[key]) acc[key] = { [xField]: key }
        acc[key][String(row[colorField])] = row[yField]
        return acc
      }, {})
    )
    return (
      <BarChart data={pivoted} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey={xField} tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => formatVal(v)} />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f1f5f9' }} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        {series.map((s, i) => (
          <Bar key={s} dataKey={s} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} maxBarSize={48} />
        ))}
      </BarChart>
    )
  }

  return (
    <BarChart data={data} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
      <XAxis dataKey={xField} tick={axisStyle} tickLine={false} axisLine={false} />
      <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => formatVal(v)} />
      <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f1f5f9' }} />
      <Bar dataKey={yField} fill={PALETTE[0]} radius={[4, 4, 0, 0]} maxBarSize={56}>
        {data.map((_, i) => (
          <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
        ))}
      </Bar>
    </BarChart>
  )
}

const LineChartRenderer: React.FC<{ parsed: ParsedChart }> = ({ parsed }) => {
  const { data, xField, yField, colorField, series } = parsed

  if (colorField && series.length > 1) {
    const pivoted = Object.values(
      data.reduce<Record<string, Record<string, unknown>>>((acc, row) => {
        const key = String(row[xField])
        if (!acc[key]) acc[key] = { [xField]: key }
        acc[key][String(row[colorField])] = row[yField]
        return acc
      }, {})
    )
    return (
      <LineChart data={pivoted} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey={xField} tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => formatVal(v)} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        {series.map((s, i) => (
          <Line key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]}
            strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        ))}
      </LineChart>
    )
  }

  return (
    <LineChart data={data} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
      <XAxis dataKey={xField} tick={axisStyle} tickLine={false} axisLine={false} />
      <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => formatVal(v)} />
      <Tooltip content={<CustomTooltip />} />
      <Line type="monotone" dataKey={yField} stroke={PALETTE[0]}
        strokeWidth={2.5} dot={{ r: 3, fill: PALETTE[0] }} activeDot={{ r: 5 }} />
    </LineChart>
  )
}

const AreaChartRenderer: React.FC<{ parsed: ParsedChart }> = ({ parsed }) => {
  const { data, xField, yField, colorField, series } = parsed

  if (colorField && series.length > 1) {
    const pivoted = Object.values(
      data.reduce<Record<string, Record<string, unknown>>>((acc, row) => {
        const key = String(row[xField])
        if (!acc[key]) acc[key] = { [xField]: key }
        acc[key][String(row[colorField])] = row[yField]
        return acc
      }, {})
    )
    return (
      <AreaChart data={pivoted} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
        <defs>
          {series.map((s, i) => (
            <linearGradient key={s} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={PALETTE[i % PALETTE.length]} stopOpacity={0.3} />
              <stop offset="95%" stopColor={PALETTE[i % PALETTE.length]} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey={xField} tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => formatVal(v)} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
        {series.map((s, i) => (
          <Area key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]}
            fill={`url(#grad-${i})`} strokeWidth={2} />
        ))}
      </AreaChart>
    )
  }

  return (
    <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
      <defs>
        <linearGradient id="grad-0" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor={PALETTE[0]} stopOpacity={0.3} />
          <stop offset="95%" stopColor={PALETTE[0]} stopOpacity={0.02} />
        </linearGradient>
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
      <XAxis dataKey={xField} tick={axisStyle} tickLine={false} axisLine={false} />
      <YAxis tick={axisStyle} tickLine={false} axisLine={false} tickFormatter={v => formatVal(v)} />
      <Tooltip content={<CustomTooltip />} />
      <Area type="monotone" dataKey={yField} stroke={PALETTE[0]}
        fill="url(#grad-0)" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
    </AreaChart>
  )
}

const PIE_ROUNDING = 2

const PieChartRenderer: React.FC<{ parsed: ParsedChart }> = ({ parsed }) => {
  const { data, xField, yField } = parsed

  const renderLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }: {
    cx: number; cy: number; midAngle: number; innerRadius: number
    outerRadius: number; percent: number; index: number
  }) => {
    const RADIAN = Math.PI / 180
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5
    const x = cx + radius * Math.cos(-midAngle * RADIAN)
    const y = cy + radius * Math.sin(-midAngle * RADIAN)
    if (percent < 0.05) return null
    return (
      <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
        {(percent * 100).toFixed(PIE_ROUNDING)}%
      </text>
    )
  }

  return (
    <PieChart margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
      <Pie data={data} cx="50%" cy="50%" outerRadius="75%" dataKey={yField} nameKey={xField}
        labelLine={false} label={renderLabel as never} paddingAngle={2}>
        {data.map((_, i) => (
          <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
        ))}
      </Pie>
      <Tooltip content={<CustomTooltip />} />
      <Legend
        formatter={(value) => <span style={{ fontSize: 11, color: '#64748b' }}>{value}</span>}
      />
    </PieChart>
  )
}

// ── Fallback: plain table ─────────────────────────────────────────────────────

const DataTable: React.FC<{ data: Record<string, unknown>[] }> = ({ data }) => {
  if (data.length === 0) return null
  const cols = Object.keys(data[0])
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead className="bg-muted/50">
          <tr>{cols.map(c => <th key={c} className="px-3 py-2 text-left font-medium text-muted-foreground">{c}</th>)}</tr>
        </thead>
        <tbody>
          {data.slice(0, 20).map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-background' : 'bg-muted/20'}>
              {cols.map(c => <td key={c} className="px-3 py-1.5 text-foreground">{formatVal(row[c])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export const ChartBlockComponent: React.FC<ChartBlock> = ({
  vega_lite_spec, title, caption,
}) => {
  const parsed = useMemo(() => {
    if (!vega_lite_spec) return null
    return parseVegaLite(vega_lite_spec as Record<string, unknown>)
  }, [vega_lite_spec])

  const chartTitle = title || (parsed?.title as string | undefined)

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
      {chartTitle && (
        <h3 className="font-semibold text-foreground text-sm">{chartTitle}</h3>
      )}

      {parsed ? (
        <ResponsiveContainer width="100%" height={280}>
          {parsed.type === 'pie' ? (
            <PieChartRenderer parsed={parsed} />
          ) : parsed.type === 'area' ? (
            <AreaChartRenderer parsed={parsed} />
          ) : parsed.type === 'line' ? (
            <LineChartRenderer parsed={parsed} />
          ) : (
            <BarChartRenderer parsed={parsed} />
          )}
        </ResponsiveContainer>
      ) : vega_lite_spec ? (
        /* Couldn't parse spec — show raw data table as fallback */
        <DataTable data={(() => {
          const spec = vega_lite_spec as Record<string, unknown>
          const d = spec.data as Record<string, unknown> | undefined
          return Array.isArray(d?.values) ? d.values as Record<string, unknown>[] : []
        })()} />
      ) : (
        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
          Нет данных для графика
        </div>
      )}

      {caption && (
        <p className="text-xs text-muted-foreground text-center italic">{caption}</p>
      )}
    </div>
  )
}
