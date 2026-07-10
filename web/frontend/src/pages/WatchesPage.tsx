import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBell, faCircleCheck } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../api/errorMessage'
import { scheduleApi, watchesApi } from '../api/endpoints'
import type { GpuOut, OccupancyChartData, RegulationOut, WatchOut } from '../api/types'
import { GpuPicker } from '../components/GpuPicker'
import { OccupancyChart } from '../components/OccupancyChart'
import { useGpuLookup } from '../api/useGpuLookup'
import { formatDateTime } from '../utils/formatDate'

const RANGE_OPTIONS = [1, 3, 5, 7, 10, 14, 30]

function nowLocalInput(offsetHours = 1): string {
  const d = new Date(Date.now() + offsetHours * 60 * 60 * 1000)
  d.setMinutes(0, 0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function WatchesPage() {
  const [serverId, setServerId] = useState<number | null>(null)
  const [gpuId, setGpuId] = useState<number | null>(null)
  const [gpu, setGpu] = useState<GpuOut | null>(null)
  const [regulation, setRegulation] = useState<RegulationOut | null>(null)
  const [days, setDays] = useState(7)
  const [chart, setChart] = useState<OccupancyChartData | null>(null)

  const [startLocal, setStartLocal] = useState(nowLocalInput(1))
  const [endLocal, setEndLocal] = useState(nowLocalInput(25))
  const [ramGb, setRamGb] = useState(4)

  const [watches, setWatches] = useState<WatchOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const gpuLookup = useGpuLookup()

  function reloadWatches() {
    watchesApi.list().then(setWatches).catch((e) => setError(errorMessage(e)))
  }

  useEffect(() => {
    scheduleApi.regulation().then(setRegulation)
    reloadWatches()
  }, [])

  useEffect(() => {
    if (!gpuId) {
      setChart(null)
      return
    }
    const rangeStart = new Date()
    rangeStart.setHours(0, 0, 0, 0)
    const rangeEnd = new Date(rangeStart.getTime() + days * 86400_000)
    scheduleApi.availability(gpuId, rangeStart.toISOString(), rangeEnd.toISOString()).then(setChart)
  }, [gpuId, regulation, days])

  const availableRangeOptions = RANGE_OPTIONS.filter((d) => !regulation || d <= regulation.booking_horizon_days)

  async function handleCreate() {
    if (!gpuId) return
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      await watchesApi.create(gpuId, new Date(startLocal).toISOString(), new Date(endLocal).toISOString(), Math.round(ramGb * 1024))
      setSuccess('Watch created — the system will auto-book the first slot that frees up matching your request.')
      reloadWatches()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCancel(id: number) {
    setError(null)
    try {
      await watchesApi.cancel(id)
      reloadWatches()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faBell} /> Watches
      </h1>
      <p className="muted">
        Ask to be auto-booked the instant enough capacity frees up on a GPU over a time range — no manual
        checking needed.
      </p>

      <div className="card">
        <h2>New watch</h2>
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
          <h2>Watch details</h2>
          {error && <div className="error-banner">{error}</div>}
          {success && (
            <div className="success-banner">
              <FontAwesomeIcon icon={faCircleCheck} /> {success}
            </div>
          )}
          <div className="row">
            <div className="field">
              <label>Watch from</label>
              <input type="datetime-local" value={startLocal} onChange={(e) => setStartLocal(e.target.value)} />
            </div>
            <div className="field">
              <label>Watch until</label>
              <input type="datetime-local" value={endLocal} onChange={(e) => setEndLocal(e.target.value)} />
            </div>
            <div className="field">
              <label>Minimum RAM needed (GB)</label>
              <input type="number" min={0.5} step={0.5} value={ramGb} onChange={(e) => setRamGb(Number(e.target.value))} />
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleCreate} disabled={busy}>
            {busy ? 'Creating…' : 'Create watch'}
          </button>
        </div>
      )}

      <div className="card">
        <h2>Active watches</h2>
        {watches?.length === 0 && <p className="muted">No active watches.</p>}
        {watches && watches.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>GPU</th>
                  <th>From</th>
                  <th>Until</th>
                  <th>Min RAM</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {watches.map((w) => {
                  const g = gpuLookup[w.gpu_id]
                  return (
                    <tr key={w.id}>
                      <td>{g ? `${g.serverName} GPU${g.indexOnServer}` : `GPU #${w.gpu_id}`}</td>
                      <td>{formatDateTime(new Date(w.range_start + 'Z'))}</td>
                      <td>{formatDateTime(new Date(w.range_end + 'Z'))}</td>
                      <td>{(w.min_ram_needed_mb / 1024).toFixed(1)} GB</td>
                      <td>
                        <button className="btn btn-sm btn-danger" onClick={() => handleCancel(w.id)}>
                          Cancel
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
