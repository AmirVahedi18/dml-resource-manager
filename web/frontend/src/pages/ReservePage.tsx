import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCalendarPlus } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { errorMessage } from '../api/errorMessage'
import { reservationsApi, scheduleApi, watchesApi } from '../api/endpoints'
import type { GpuOut, OccupancyChartData, RegulationOut, ServerOverviewOut } from '../api/types'
import { AvailabilityGlance } from '../components/AvailabilityGlance'
import { DatePicker } from '../components/DatePicker'
import { InfoTooltip } from '../components/InfoTooltip'
import { MyReservationsCard } from '../components/MyReservationsCard'
import { TimeSelect } from '../components/TimeSelect'
import { useToast } from '../components/Toast'
import { fadeVariants } from '../motion'
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
  const [gpuId, setGpuId] = useState<number | null>(null)
  const [gpu, setGpu] = useState<GpuOut | null>(null)
  const [regulation, setRegulation] = useState<RegulationOut | null>(null)
  const [days, setDays] = useState(7)
  const [chart, setChart] = useState<OccupancyChartData | null>(null)

  const [startDate, setStartDate] = useState(() => dateStrFromParts(defaultStartParts('UTC')))
  const [startValue, setStartValue] = useState(() => new Date(Date.now() + 60 * 60 * 1000).toISOString())
  const [durationHours, setDurationHours] = useState(1)
  const [ramGb, setRamGb] = useState(4)
  const [description, setDescription] = useState('')
  const [freeRamMb, setFreeRamMb] = useState<number | null>(null)

  const [busy, setBusy] = useState(false)
  const [watchBusy, setWatchBusy] = useState(false)
  // Bumping this refreshes the availability glance + My Reservations after a booking.
  const [reloadSignal, setReloadSignal] = useState(0)
  const toast = useToast()

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
    const rangeStart = new Date()
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

  // Preselect a GPU straight from the "Available now" glance.
  function handlePick(_serverId: number, pickedGpu: GpuOut) {
    setGpuId(pickedGpu.id)
    setGpu(pickedGpu)
  }

  // Re-checked on every overview refresh (see AvailabilityGlance's background poll) so a GPU or
  // its server being deactivated mid-booking is caught here -- at the GPU-selection/form stage --
  // rather than only surfacing as a rejected submit at the very end.
  function handleServersUpdate(servers: ServerOverviewOut[]) {
    if (!gpuId) return
    for (const server of servers) {
      const found = server.gpus.find((g) => g.id === gpuId)
      if (!found) continue
      const active = server.is_active && found.is_active
      if (!active) {
        toast.error('This GPU just became unavailable (it was deactivated). Please pick another one.')
        setGpuId(null)
        setGpu(null)
      } else if (!gpu?.is_active) {
        setGpu((prev) => (prev ? { ...prev, is_active: true } : prev))
      }
      return
    }
  }

  const startUtc = useMemo(() => new Date(startValue), [startValue])
  const endUtc = useMemo(() => new Date(startUtc.getTime() + durationHours * 3600_000), [startUtc, durationHours])

  // Hypothetical booking preview, shown translucently in the availability diagram as the
  // user fills in the form — updates live as start/duration/RAM change.
  const preview = useMemo(
    () => (gpuId ? { start: startUtc.toISOString(), end: endUtc.toISOString(), ramMb: Math.round(ramGb * 1024) } : null),
    [gpuId, startUtc, endUtc, ramGb],
  )

  // Debounced: how much RAM is actually free throughout the picked window, so the user can
  // judge feasibility before submitting -- durationHours changes on every keystroke, so this
  // avoids firing a request per digit typed.
  useEffect(() => {
    if (!gpuId) {
      setFreeRamMb(null)
      return
    }
    setFreeRamMb(null)
    const start = startUtc.toISOString()
    const end = endUtc.toISOString()
    const timer = setTimeout(() => {
      scheduleApi.freeRam(gpuId, start, end).then((r) => setFreeRamMb(r.free_ram_mb))
    }, 300)
    return () => clearTimeout(timer)
  }, [gpuId, startUtc, endUtc])

  // Back to the same defaults the form starts with, so a repeat booking doesn't inherit the
  // just-submitted window.
  function resetForm() {
    setStartDate(dateStrFromParts(defaultStartParts(tz)))
    setStartValue(new Date(Date.now() + 60 * 60 * 1000).toISOString())
    setDurationHours(1)
    setRamGb(4)
    setDescription('')
  }

  async function handleSubmit() {
    if (!gpuId || !description.trim()) return
    if (!gpu?.is_active) {
      toast.error('This GPU is no longer available (it was deactivated). Please pick another one.')
      return
    }
    setBusy(true)
    try {
      await reservationsApi.create(
        gpuId, startUtc.toISOString(), endUtc.toISOString(), Math.round(ramGb * 1024), description.trim()
      )
      toast.success('Reservation created.')
      resetForm()
      setReloadSignal((n) => n + 1) // refresh glance + My Reservations
      const rangeStart = new Date()
      const rangeEnd = new Date(rangeStart.getTime() + days * 86400_000)
      scheduleApi.availability(gpuId, rangeStart.toISOString(), rangeEnd.toISOString()).then(setChart)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateWatch() {
    if (!gpuId || !description.trim()) return
    if (!gpu?.is_active) {
      toast.error('This GPU is no longer available (it was deactivated). Please pick another one.')
      return
    }
    setWatchBusy(true)
    try {
      await watchesApi.create(
        gpuId, startUtc.toISOString(), endUtc.toISOString(), Math.round(ramGb * 1024), description.trim()
      )
      toast.success('Watch created — the system will auto-book the moment this window has enough free RAM.')
      setReloadSignal((n) => n + 1) // refresh My Reservations' watches list
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setWatchBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faCalendarPlus} /> Reserve GPU
      </h1>

      {/* At-a-glance live availability — the primary entry point; picking a GPU here
          preselects it in the form and scrolls down to it. Also hosts the range selection
          and availability chart for whichever GPU is currently selected. */}
      <AvailabilityGlance
        selectedGpuId={gpuId}
        onPick={handlePick}
        reloadSignal={reloadSignal}
        days={days}
        availableRangeOptions={availableRangeOptions}
        onDaysChange={setDays}
        chart={chart}
        tz={tz}
        preview={preview}
        onServersUpdate={handleServersUpdate}
      />

      <div className="card card-feature">
        <AnimatePresence mode="wait">
          {!gpuId && (
            <motion.p key="prompt" className="muted picker-placeholder" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              Pick a GPU above to see its availability and book a slot.
            </motion.p>
          )}

          {gpuId && (!gpu || !regulation) && (
            <motion.p key="loading" className="muted" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              Loading…
            </motion.p>
          )}

          {gpuId && gpu && regulation && (
            <motion.div key="form" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            <h2>Reservation details</h2>
            <div className="row row-tight">
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
                <label>RAM (GB, max {Math.min(regulation.max_ram_per_reservation_gb, gpu.total_ram_mb / 1024).toFixed(0)})</label>
                <input type="number" min={0.5} step={0.5} value={ramGb} onChange={(e) => setRamGb(Number(e.target.value))} />
              </div>
            </div>
            <div className="row">
              <div className="field">
                <label>Description (required — what is this GPU time for?)</label>
                <input
                  type="text"
                  required
                  maxLength={300}
                  placeholder="e.g. Project name, paper, experiment…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
            <div className="reserve-window-info">
              <p className="muted">
                {freeRamMb == null ? (
                  'Checking free RAM for this window…'
                ) : (
                  <>
                    Free during this window: <strong>{(freeRamMb / 1024).toFixed(1)} GB</strong> of{' '}
                    {(gpu.total_ram_mb / 1024).toFixed(0)} GB
                  </>
                )}
              </p>
              <p className="muted">
                Ends: <span className="mono">{formatDateTime(endUtc, tz)}</span> ({tz})
              </p>
            </div>
            <div className="reserve-actions">
              <button
                className="btn btn-primary btn-lg"
                onClick={handleSubmit}
                disabled={busy || !description.trim() || !gpu.is_active}
              >
                {busy ? 'Reserving…' : 'Reserve this GPU'}
              </button>
              <button
                className="btn btn-secondary btn-lg"
                onClick={handleCreateWatch}
                disabled={watchBusy || !description.trim() || !gpu.is_active}
              >
                {watchBusy ? 'Creating watch…' : 'Watch this instead'}
              </button>
              <InfoTooltip text="Not enough free RAM right now for this window? Watch it instead — you'll be auto-booked the moment it frees up." />
            </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <MyReservationsCard reloadSignal={reloadSignal} />
    </div>
  )
}
