import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { RankedUsageOut } from '../api/types'

export function UsageBarChart({ data }: { data: RankedUsageOut }) {
  const chartData = data.labels
    .map((label, i) => ({ label, value: data.values[i] }))
    .sort((a, b) => a.value - b.value) // ascending: layout="vertical" stacks bottom-to-top

  const height = Math.max(200, 60 + chartData.length * 34)

  if (chartData.length === 0) return <p className="muted">No reservations in that range.</p>

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 48, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: 'var(--ink-muted)' }}
          stroke="var(--border)"
          label={{ value: data.unit, position: 'insideBottom', offset: -4, fontSize: 11, fill: 'var(--ink-muted)' }}
        />
        <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 11, fill: 'var(--ink-muted)' }} stroke="var(--border)" />
        <Tooltip
          formatter={(value) => `${Number(value).toFixed(1)} ${data.unit}`}
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
          labelStyle={{ color: 'var(--ink-muted)' }}
        />
        <Bar dataKey="value" fill="#2a78d6">
          <LabelList dataKey="value" position="right" formatter={(v) => Number(v).toFixed(1)} style={{ fontSize: 11, fill: 'var(--ink)' }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
