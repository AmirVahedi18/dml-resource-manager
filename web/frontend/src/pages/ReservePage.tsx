import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCalendarPlus, faCircleCheck } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useMemo, useState } from 'react'
import { errorMessage } from '../api/errorMessage'
import { reservationsApi, scheduleApi } from '../api/endpoints'
import type { GpuOut, OccupancyChartData, RegulationOut } from '../api/types'
import { DatePicker } from '../components/DatePicker'
import { GpuPicker } from '../components/GpuPicker'
import { MyReservationsCard } from '../components/MyReservationsCard'
import { OccupancyChart } from '../components/OccupancyChart'
import { TimeSelect } from '../components/TimeSelect'
import { formatDateTime } from '../utils/formatDate'

const RANGE_OPTIONS = [1, 3, 5, 7, 10, 14, 30]

const pad = (n: number) => String(n).padStart(2, '0')

/** y/m/d/h/m/s of `date`, as displayed in the IANA zone `tz`. */
function partsInTz(date: Date, tz: string) {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  const map: Record<string, string> = {}
  for (const p of dtf.formatToParts(date)) {
    if (p.type !== 'literal') map[p.type] = p.value
  }
  return {
    year: Number(map.year),
    month: Number(map.month),
    day: Number(map.day),
    hour: Number(map.hour),
    minute: Number(map.minute),
    second: Number(map.second),
  }
}

function dateStrFromParts(p: { year: number; month: number; day: number }): string {
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`
}

function timeStrFromParts(p: { hour: number; minute: number }): string {
  return `${pad(p.hour)}:${pad(p.minute)}`
}

/** The wall-clock date/time as shown in `tz`, converted to the equivalent UTC instant. */
function zonedTimeToUtc(dateStr: string, timeStr: string, tz: string): Date {
  const [year, month, day] = dateStr.split('-').map(Number)
  const [hour, minute] = timeStr.split(':').map(Number)
  const utcGuess = Date.UTC(year, month - 1, day, hour, minute)
  const asIfUtc = partsInTz(new Date(utcGuess), tz)
  const reinterpreted = Date.UTC(asIfUtc.year, asIfUtc.month - 1, asIfUtc.day, asIfUtc.hour, asIfUtc.minute, asIfUtc.second)
  return new Date(utcGuess - (reinterpreted - utcGuess))
}

function zonedMidnightUtc(dateStr: string, tz: string): Date {
  return zonedTimeToUtc(dateStr, '00:00', tz)
}

function defaultStartParts(tz: string) {
  return partsInTz(new Date(Date.now() + 60 * 60 * 1000), tz)
}

interface SlotOption {
  /** UTC instant, ISO — this is exactly what gets submitted, never re-derived from a label. */
  value: string
  /** Wall-clock label in `tz`, for display only. */
  label: string
}

/**
 * Reservation slots are aligned to raw UTC epoch on the backend (`is_slot_aligned` in
 * time_utils.py), not to the app's configured timezone's wall clock. Zones like Asia/Tehran
 * (UTC+3:30) have a fractional-hour offset, so "clean" local hour marks (16:00, 17:00, ...)
 * do NOT land on UTC slot boundaries. To always offer only submittable slots, generate the
 * candidate instants directly in UTC-aligned space for the selected local calendar day, and
 * only use `tz` to produce a human-readable label for each one.
 */
function slotOptionsForLocalDay(dateStr: string, tz: string, slotMinutes: number, notBefore: Date | null): SlotOption[] {
  const dayStartMs = zonedMidnightUtc(dateStr, tz).getTime()
  const dayEndMs = dayStartMs + 24 * 3600_000
  const slotMs = slotMinutes * 60_000
  const opts: SlotOption[] = []
  for (let t = Math.ceil(dayStartMs / slotMs) * slotMs; t < dayEndMs; t += slotMs) {
    if (notBefore && t < notBefore.getTime()) continue
    const d = new Date(t)
    opts.push({ value: d.toISOString(), label: timeStrFromParts(partsInTz(d, tz)) })
  }
  return opts
}

export function ReservePage() {
  const [serverId, setServerId] = useState<number | null>(null)
  const [gpuId, setGpuId] = useState<number | null>(null)
  const [gpu, setGpu] = useState<GpuOut | null>(null)
  const [regulation, setRegulation] = useState<RegulationOut | null>(null)
  const [days, setDays] = useState(7)
  const [chart, setChart] = useState<OccupancyChartData | null>(null)

  const [startDate, setStartDate] = useState(() => dateStrFromParts(defaultStartParts('UTC')))
  const [startValue, setStartValue] = useState(() => new Date(Date.now() + 60 * 60 * 1000).toISOString())
  const [durationHours, setDurationHours] = useState(1)
  const [ramGb, setRamGb] = useState(4)

  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const tz = regulation?.timezone ?? 'UTC'
  const slotMinutes = regulation?.min_reservation_slot_minutes ?? 30

  useEffect(() => {
    scheduleApi.regulation().then(setRegulation)
  }, [])

  // Re-seed the default day once the app's real timezone is known (replaces the 'UTC' guess
  // used for the initial state before the /api/regulation response arrives).
  useEffect(() => {
    setStartDate(dateStrFromParts(defaultStartParts(tz)))
  }, [tz])

  useEffect(() => {
    if (!gpuId) {
      setChart(null)
      return
    }
    const today = dateStrFromParts(partsInTz(new Date(), tz))
    const rangeStart = zonedMidnightUtc(today, tz)
    const rangeEnd = new Date(rangeStart.getTime() + days * 86400_000)
    scheduleApi.availability(gpuId, rangeStart.toISOString(), rangeEnd.toISOString()).then(setChart)
  }, [gpuId, regulation, tz, days])

  const availableRangeOptions = RANGE_OPTIONS.filter((d) => !regulation || d <= regulation.booking_horizon_days)

  const todayStr = dateStrFromParts(partsInTz(new Date(), tz))
  const isToday = startDate === todayStr
  const maxDateStr = useMemo(() => {
    const horizonDays = regulation?.booking_horizon_days ?? 14
    const todayMidnightUtc = zonedMidnightUtc(todayStr, tz)
    return dateStrFromParts(partsInTz(new Date(todayMidnightUtc.getTime() + horizonDays * 86400_000), tz))
  }, [todayStr, tz, regulation])

  const slotOptions = useMemo(
    () => slotOptionsForLocalDay(startDate, tz, slotMinutes, isToday ? new Date() : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [startDate, tz, slotMinutes, isToday],
  )

  useEffect(() => {
    if (slotOptions.length > 0 && !slotOptions.some((o) => o.value === startValue)) {
      setStartValue(slotOptions[0].value)
    }
  }, [slotOptions, startValue])

  function handleDateChange(value: string) {
    setStartDate(value < todayStr ? todayStr : value)
  }

  const startUtc = useMemo(() => new Date(startValue), [startValue])
  const endUtc = useMemo(() => new Date(startUtc.getTime() + durationHours * 3600_000), [startUtc, durationHours])

  async function handleSubmit() {
    if (!gpuId) return
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      await reservationsApi.create(gpuId, startUtc.toISOString(), endUtc.toISOString(), Math.round(ramGb * 1024))
      setSuccess('Reservation created.')
      const today = dateStrFromParts(partsInTz(new Date(), tz))
      const rangeStart = zonedMidnightUtc(today, tz)
      const rangeEnd = new Date(rangeStart.getTime() + days * 86400_000)
      scheduleApi.availability(gpuId, rangeStart.toISOString(), rangeEnd.toISOString()).then(setChart)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faCalendarPlus} /> Reserve GPU
      </h1>

      <MyReservationsCard />

      <div className="card">
        <GpuPicker
          serverId={serverId}
          gpuId={gpuId}
          onServerChange={setServerId}
          onGpuChange={(id, g) => {
            setGpuId(id)
            setGpu(g)
          }}
        />
        <div className="field">
          <label>Range</label>
          <div className="segmented">
            {availableRangeOptions.map((d) => (
              <button
                key={d}
                type="button"
                className={`segmented-option${days === d ? ' segmented-option-active' : ''}`}
                onClick={() => setDays(d)}
              >
                {d === 1 ? 'Today' : `${d}d`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {chart && (
        <div className="card">
          <h2>Availability — next {days} {days === 1 ? 'day' : 'days'}</h2>
          <OccupancyChart data={chart} />
        </div>
      )}

      {chart && chart.segments.length > 0 && (
        <div className="card">
          <h2>Reservations in range</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>RAM</th>
                </tr>
              </thead>
              <tbody>
                {chart.segments.map((s) => (
                  <tr key={s.reservation_id}>
                    <td>{s.user}</td>
                    <td>{formatDateTime(new Date(s.start))}</td>
                    <td>{formatDateTime(new Date(s.end))}</td>
                    <td>{(s.ram_mb / 1024).toFixed(1)} GB</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {gpu && regulation && (
        <div className="card">
          <h2>Reservation details</h2>
          {error && <div className="error-banner">{error}</div>}
          {success && (
            <div className="success-banner">
              <FontAwesomeIcon icon={faCircleCheck} /> {success}
            </div>
          )}
          <div className="row">
            <div className="field">
              <label>Start Date ({tz})</label>
              <DatePicker value={startDate} min={todayStr} max={maxDateStr} onChange={handleDateChange} />
            </div>
            <div className="field">
              <label>Start Time ({tz})</label>
              <TimeSelect
                value={startValue}
                options={slotOptions}
                disabled={slotOptions.length === 0}
                onChange={setStartValue}
              />
            </div>
            <div className="field">
              <label>Duration (hours, max {regulation.max_duration_hours})</label>
              <input
                type="number"
                min={slotMinutes / 60}
                step={slotMinutes / 60}
                max={regulation.max_duration_hours}
                value={durationHours}
                onChange={(e) => setDurationHours(Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>RAM (GB, max {(Math.min(regulation.max_ram_per_reservation_mb, gpu.total_ram_mb) / 1024).toFixed(0)})</label>
              <input type="number" min={0.5} step={0.5} value={ramGb} onChange={(e) => setRamGb(Number(e.target.value))} />
            </div>
          </div>
          <p className="muted">Ends: {formatDateTime(endUtc, tz)} ({tz})</p>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={busy}>
            {busy ? 'Reserving…' : 'Reserve'}
          </button>
        </div>
      )}
    </div>
  )
}
