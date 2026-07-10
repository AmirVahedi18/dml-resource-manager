import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { OccupancyChartData } from '../api/types'
import { CATEGORICAL_COLORS, MAX_NAMED_USERS, OTHER_COLOR, colorMap, displayUnit, rankUsers } from './chartColors'

function fmtBucketLabel(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtShort(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function OccupancyChart({ data }: { data: OccupancyChartData }) {
  const [view, setView] = useState<'bars' | 'timeline'>('bars')
  const { label: unitLabel, divisor } = displayUnit(data.capacity_mb)

  const totals = useMemo(() => {
    const totals: Record<string, number> = {}
    for (const seg of data.segments) totals[seg.user] = (totals[seg.user] ?? 0) + seg.ram_mb
    return totals
  }, [data.segments])

  const ranked = useMemo(() => rankUsers(totals), [totals])
  const colors = useMemo(() => colorMap(ranked), [ranked])
  const named = ranked.slice(0, MAX_NAMED_USERS)
  const other = ranked.slice(MAX_NAMED_USERS)

  const barData = useMemo(
    () =>
      data.buckets.map((b) => {
        const row: Record<string, string | number> = { label: fmtBucketLabel(b.start) }
        for (const name of named) row[name] = (b.usage[name] ?? 0) / divisor
        if (other.length) {
          row['Other'] = other.reduce((sum, name) => sum + (b.usage[name] ?? 0), 0) / divisor
        }
        return row
      }),
    [data.buckets, named, other, divisor]
  )

  const capacityVal = data.capacity_mb / divisor
  const rangeStartMs = new Date(data.range_start).getTime()
  const rangeEndMs = new Date(data.range_end).getTime()
  const totalSpan = Math.max(rangeEndMs - rangeStartMs, 1)

  // Evenly spaced tick labels for the timeline's time ruler. On short ranges we include the
  // hour; on multi-day ranges the date alone keeps labels from crowding.
  const axisTicks = useMemo(() => {
    const count = 5
    const spanDays = totalSpan / 86400_000
    const withHour = spanDays <= 2
    return Array.from({ length: count }, (_, i) => {
      const frac = i / (count - 1)
      const d = new Date(rangeStartMs + frac * totalSpan)
      const label = d.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        ...(withHour ? { hour: '2-digit', minute: '2-digit' } : {}),
      })
      return { frac, label }
    })
  }, [rangeStartMs, totalSpan])

  return (
    <div>
      {/* Real buttons in a tablist so the view switch is keyboard- and SR-accessible. */}
      <div className="tabs" role="tablist" aria-label="Occupancy view">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'bars'}
          className={`tab${view === 'bars' ? ' active' : ''}`}
          onClick={() => setView('bars')}
        >
          Bars
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'timeline'}
          className={`tab${view === 'timeline' ? ' active' : ''}`}
          onClick={() => setView('timeline')}
        >
          Timeline
        </button>
      </div>

      {data.segments.length === 0 && <p className="muted">Fully free in this range.</p>}

      {view === 'bars' && (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={barData} margin={{ top: 8, right: 12, left: 0, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="label"
              angle={-45}
              textAnchor="end"
              interval="preserveStartEnd"
              height={60}
              tick={{ fontSize: 11, fill: 'var(--ink-muted)' }}
              stroke="var(--border)"
            />
            <YAxis
              label={{ value: `RAM used (${unitLabel})`, angle: -90, position: 'insideLeft', fontSize: 11, fill: 'var(--ink-muted)' }}
              tick={{ fontSize: 11, fill: 'var(--ink-muted)' }}
              stroke="var(--border)"
            />
            <Tooltip
              formatter={(value) => `${Number(value).toFixed(1)} ${unitLabel}`}
              contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
              labelStyle={{ color: 'var(--ink-muted)' }}
            />
            {named.map((name, i) => (
              <Bar key={name} dataKey={name} stackId="usage" fill={CATEGORICAL_COLORS[i]} />
            ))}
            {other.length > 0 && <Bar dataKey="Other" stackId="usage" fill={OTHER_COLOR} />}
            <ReferenceLine y={capacityVal} stroke="currentColor" strokeDasharray="4 4" strokeOpacity={0.6} />
          </BarChart>
        </ResponsiveContainer>
      )}

      {view === 'timeline' && (
        <div>
          {ranked.length === 0 && <p className="muted">No reservations in this range.</p>}
          {ranked.map((name) => (
            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <div className="occ-timeline-label muted">{name}</div>
              <div
                style={{
                  position: 'relative',
                  flex: 1,
                  height: 22,
                  background: 'var(--surface-alt)',
                  borderRadius: 4,
                }}
              >
                {data.segments
                  .filter((seg) => seg.user === name)
                  .map((seg) => {
                    const segStart = new Date(seg.start).getTime()
                    const segEnd = new Date(seg.end).getTime()
                    const left = ((segStart - rangeStartMs) / totalSpan) * 100
                    const width = ((segEnd - segStart) / totalSpan) * 100
                    return (
                      <div
                        key={seg.reservation_id}
                        title={`${(seg.ram_mb / divisor).toFixed(1)} ${unitLabel} · ${fmtShort(seg.start)} → ${fmtShort(seg.end)}`}
                        style={{
                          position: 'absolute',
                          left: `${Math.max(left, 0)}%`,
                          width: `${Math.max(width, 0.5)}%`,
                          top: 2,
                          bottom: 2,
                          background: colors[name] ?? OTHER_COLOR,
                          borderRadius: 3,
                        }}
                      />
                    )
                  })}
              </div>
            </div>
          ))}

          {/* Time ruler so the floating bars are readable against actual dates/times. */}
          {ranked.length > 0 && (
            <div className="occ-axis">
              <div className="occ-timeline-label" aria-hidden />
              <div className="occ-axis-track">
                {axisTicks.map((t, i) => (
                  <span
                    key={i}
                    className="occ-axis-tick"
                    style={{
                      left: `${t.frac * 100}%`,
                      transform: i === 0 ? 'none' : i === axisTicks.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)',
                    }}
                  >
                    {t.label}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="chart-legend">
        {named.map((name, i) => (
          <span key={name} className="chart-legend-item">
            <span className="chart-legend-swatch" style={{ background: CATEGORICAL_COLORS[i] }} />
            {name}
          </span>
        ))}
        {other.length > 0 && (
          <span className="chart-legend-item">
            <span className="chart-legend-swatch" style={{ background: OTHER_COLOR }} />
            Other ({other.length})
          </span>
        )}
        <span className="chart-legend-item muted">Capacity: {capacityVal.toFixed(0)} {unitLabel}</span>
      </div>
    </div>
  )
}
