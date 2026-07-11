import { AnimatePresence, motion } from 'framer-motion'
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
import { fadeSlideVariants, fadeVariants } from '../motion'

function fmtBucketLabel(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtShort(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

interface PreviewWindow {
  start: string
  end: string
  ramMb: number
}

export function OccupancyChart({ data, preview = null }: { data: OccupancyChartData; preview?: PreviewWindow | null }) {
  const [view, setView] = useState<'bars' | 'timeline'>(() => (preview ? 'timeline' : 'bars'))
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

  const previewStartMs = preview ? new Date(preview.start).getTime() : null
  const previewEndMs = preview ? new Date(preview.end).getTime() : null
  const hasPreview = !!preview && preview.ramMb > 0 && previewStartMs !== null && previewEndMs !== null && previewEndMs > previewStartMs

  const barData = useMemo(
    () =>
      data.buckets.map((b) => {
        const row: Record<string, string | number> = { label: fmtBucketLabel(b.start) }
        for (const name of named) row[name] = (b.usage[name] ?? 0) / divisor
        if (other.length) {
          row['Other'] = other.reduce((sum, name) => sum + (b.usage[name] ?? 0), 0) / divisor
        }
        if (hasPreview) {
          const bucketStartMs = new Date(b.start).getTime()
          const bucketEndMs = new Date(b.end).getTime()
          const overlaps = bucketStartMs < (previewEndMs as number) && bucketEndMs > (previewStartMs as number)
          row['__preview'] = overlaps ? preview!.ramMb / divisor : 0
        }
        return row
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data.buckets, named, other, divisor, hasPreview, previewStartMs, previewEndMs, preview?.ramMb]
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

      <AnimatePresence>
        {data.segments.length === 0 && (
          <motion.p className="muted" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            Fully free in this range.
          </motion.p>
        )}
      </AnimatePresence>

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
              domain={[0, capacityVal]}
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
            {hasPreview && (
              <Bar
                dataKey="__preview"
                stackId="usage"
                fill="var(--accent)"
                fillOpacity={0.4}
                stroke="var(--accent)"
                strokeDasharray="3 3"
              />
            )}
            <ReferenceLine y={capacityVal} stroke="currentColor" strokeDasharray="4 4" strokeOpacity={0.6} />
          </BarChart>
        </ResponsiveContainer>
      )}

      {view === 'timeline' && (
        <div>
          <AnimatePresence>
            {ranked.length === 0 && !hasPreview && (
              <motion.p className="muted" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                No reservations in this range.
              </motion.p>
            )}
          </AnimatePresence>
          <AnimatePresence>
          {hasPreview && (
            <motion.div
              key="__preview"
              layout
              variants={fadeSlideVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}
            >
              <div className="occ-timeline-label muted">Your booking</div>
              <div
                style={{
                  position: 'relative',
                  flex: 1,
                  height: 22,
                  background: 'var(--surface-alt)',
                  borderRadius: 4,
                  overflow: 'hidden',
                }}
              >
                {(() => {
                  const segStart = Math.max(previewStartMs as number, rangeStartMs)
                  const segEnd = Math.min(previewEndMs as number, rangeStartMs + totalSpan)
                  if (segEnd <= segStart) return null
                  const left = ((segStart - rangeStartMs) / totalSpan) * 100
                  const width = Math.max(((segEnd - segStart) / totalSpan) * 100, 0.5)
                  return (
                    <div
                      title={`${(preview!.ramMb / divisor).toFixed(1)} ${unitLabel} · ${fmtShort(preview!.start)} → ${fmtShort(preview!.end)} (hypothetical)`}
                      style={{
                        position: 'absolute',
                        left: `${Math.min(Math.max(left, 0), 100)}%`,
                        width: `${width}%`,
                        top: 2,
                        bottom: 2,
                        background: 'var(--accent)',
                        opacity: 0.45,
                        border: '1px dashed var(--accent)',
                        borderRadius: 3,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                      }}
                    >
                      <span className="occ-segment-label">{(preview!.ramMb / divisor).toFixed(1)} {unitLabel}</span>
                    </div>
                  )
                })()}
              </div>
            </motion.div>
          )}
          {ranked.map((name) => (
            <motion.div
              key={name}
              layout
              variants={fadeSlideVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}
            >
              <div className="occ-timeline-label muted">{name}</div>
              <div
                style={{
                  position: 'relative',
                  flex: 1,
                  height: 22,
                  background: 'var(--surface-alt)',
                  borderRadius: 4,
                  overflow: 'hidden',
                }}
              >
                {data.segments
                  .filter((seg) => seg.user === name)
                  .map((seg) => {
                    // Clip to the visible range on both ends — a reservation that starts
                    // before rangeStart or ends after rangeEnd must not push the bar's
                    // left/width past the track's 0–100% bounds (that's what caused bars
                    // to spill out past the card edge).
                    const segStart = Math.max(new Date(seg.start).getTime(), rangeStartMs)
                    const segEnd = Math.min(new Date(seg.end).getTime(), rangeStartMs + totalSpan)
                    const left = ((segStart - rangeStartMs) / totalSpan) * 100
                    const width = Math.max(((segEnd - segStart) / totalSpan) * 100, 0.5)
                    return (
                      <div
                        key={seg.reservation_id}
                        title={`${(seg.ram_mb / divisor).toFixed(1)} ${unitLabel} · ${fmtShort(seg.start)} → ${fmtShort(seg.end)}`}
                        style={{
                          position: 'absolute',
                          left: `${Math.min(Math.max(left, 0), 100)}%`,
                          width: `${width}%`,
                          top: 2,
                          bottom: 2,
                          background: colors[name] ?? OTHER_COLOR,
                          borderRadius: 3,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          overflow: 'hidden',
                        }}
                      >
                        <span className="occ-segment-label">{(seg.ram_mb / divisor).toFixed(1)} {unitLabel}</span>
                      </div>
                    )
                  })}
              </div>
            </motion.div>
          ))}
          </AnimatePresence>

          {/* Time ruler so the floating bars are readable against actual dates/times. */}
          <AnimatePresence>
            {(ranked.length > 0 || hasPreview) && (
              <motion.div className="occ-axis" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
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
              </motion.div>
            )}
          </AnimatePresence>
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
        {hasPreview && (
          <span className="chart-legend-item">
            <span className="chart-legend-swatch chart-legend-swatch-preview" />
            Your booking (preview)
          </span>
        )}
        <span className="chart-legend-item muted">Capacity: {capacityVal.toFixed(0)} {unitLabel}</span>
      </div>
    </div>
  )
}
