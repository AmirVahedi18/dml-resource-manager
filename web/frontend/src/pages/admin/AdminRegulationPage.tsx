import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleCheck, faScaleBalanced } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminRegulationApi } from '../../api/endpoints'
import type { RegulationOut } from '../../api/types'

const FIELDS: { key: keyof RegulationOut; label: string; help: string }[] = [
  { key: 'max_ram_per_reservation_mb', label: 'Max RAM per reservation (MB)', help: 'Upper bound on RAM a single reservation may request.' },
  { key: 'max_duration_hours', label: 'Max reservation duration (hours)', help: 'Longest a single reservation window may span.' },
  { key: 'booking_horizon_days', label: 'Booking horizon (days)', help: 'How far in advance a reservation may start.' },
  { key: 'min_reservation_slot_minutes', label: 'Time-slot granularity (minutes)', help: 'Reservations must start/end aligned to this grid.' },
  { key: 'max_active_reservations_per_user', label: 'Max active reservations per user', help: 'How many upcoming reservations a student may hold at once.' },
  { key: 'min_cancellation_notice_minutes', label: 'Min. self-cancellation notice (minutes)', help: '0 disables the cutoff. Admin cancellations always bypass this.' },
]

export function AdminRegulationPage() {
  const [regulation, setRegulation] = useState<RegulationOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    adminRegulationApi.get().then(setRegulation).catch((e) => setError(errorMessage(e)))
  }, [])

  async function handleSave() {
    if (!regulation) return
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const updated = await adminRegulationApi.update(regulation)
      setRegulation(updated)
      setSuccess('Regulation updated.')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faScaleBalanced} /> Regulation
      </h1>
      <div className="card" style={{ maxWidth: 480 }}>
        {error && <div className="error-banner">{error}</div>}
        {success && (
          <div className="success-banner">
            <FontAwesomeIcon icon={faCircleCheck} /> {success}
          </div>
        )}
        {regulation &&
          FIELDS.map((f) => (
            <div className="field" key={f.key}>
              <label>{f.label}</label>
              <input
                type="number"
                min={0}
                value={regulation[f.key]}
                onChange={(e) => setRegulation({ ...regulation, [f.key]: Number(e.target.value) })}
              />
              <span className="muted" style={{ fontSize: 12 }}>
                {f.help}
              </span>
            </div>
          ))}
        <button className="btn btn-primary" onClick={handleSave} disabled={busy || !regulation}>
          {busy ? 'Saving…' : 'Save regulation'}
        </button>
      </div>
    </div>
  )
}
