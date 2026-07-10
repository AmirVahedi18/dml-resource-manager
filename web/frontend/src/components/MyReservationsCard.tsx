import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCalendarDays } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../api/errorMessage'
import { reservationsApi } from '../api/endpoints'
import type { ReservationOut } from '../api/types'
import { useGpuLookup } from '../api/useGpuLookup'
import { formatDateTime } from '../utils/formatDate'
import { ConfirmDialog } from './ConfirmDialog'

export function MyReservationsCard() {
  const [reservations, setReservations] = useState<ReservationOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const gpuLookup = useGpuLookup()

  const [pendingCancel, setPendingCancel] = useState<ReservationOut | null>(null)
  const [cancelBusy, setCancelBusy] = useState(false)

  function reload() {
    reservationsApi.list(true).then(setReservations).catch((e) => setError(errorMessage(e)))
  }

  useEffect(reload, [])

  async function confirmCancel() {
    if (!pendingCancel) return
    setError(null)
    setCancelBusy(true)
    try {
      await reservationsApi.cancel(pendingCancel.id)
      setPendingCancel(null)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  return (
    <div className="card">
      <h2>
        <FontAwesomeIcon icon={faCalendarDays} /> My Reservations
      </h2>
      {error && <div className="error-banner">{error}</div>}
      {reservations === null && <p className="muted">Loading…</p>}
      {reservations?.length === 0 && <p className="muted">No upcoming reservations.</p>}
      {reservations && reservations.length > 0 && (
        <>
          <div className="table-scroll reservation-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>GPU</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>RAM</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {reservations.map((r) => {
                  const gpu = gpuLookup[r.gpu_id]
                  return (
                    <tr key={r.id}>
                      <td>{gpu ? `${gpu.serverName} GPU${gpu.indexOnServer}` : `GPU #${r.gpu_id}`}</td>
                      <td>{formatDateTime(new Date(r.start_time + 'Z'))}</td>
                      <td>{formatDateTime(new Date(r.end_time + 'Z'))}</td>
                      <td>{(r.ram_mb / 1024).toFixed(1)} GB</td>
                      <td>
                        <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(r)}>
                          Cancel
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="reservation-cards">
            {reservations.map((r) => {
              const gpu = gpuLookup[r.gpu_id]
              return (
                <div className="reservation-card" key={r.id}>
                  <div className="reservation-card-title">
                    {gpu ? `${gpu.serverName} GPU${gpu.indexOnServer}` : `GPU #${r.gpu_id}`}
                  </div>
                  <div className="reservation-card-row">
                    <span className="muted">Start</span>
                    <span>{formatDateTime(new Date(r.start_time + 'Z'))}</span>
                  </div>
                  <div className="reservation-card-row">
                    <span className="muted">End</span>
                    <span>{formatDateTime(new Date(r.end_time + 'Z'))}</span>
                  </div>
                  <div className="reservation-card-row">
                    <span className="muted">RAM</span>
                    <span>{(r.ram_mb / 1024).toFixed(1)} GB</span>
                  </div>
                  <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(r)}>
                    Cancel
                  </button>
                </div>
              )
            })}
          </div>
        </>
      )}

      <ConfirmDialog
        open={pendingCancel !== null}
        title="Cancel reservation?"
        message={
          pendingCancel && (
            <>
              This will cancel your reservation for{' '}
              <strong>
                {gpuLookup[pendingCancel.gpu_id]
                  ? `${gpuLookup[pendingCancel.gpu_id].serverName} GPU${gpuLookup[pendingCancel.gpu_id].indexOnServer}`
                  : `GPU #${pendingCancel.gpu_id}`}
              </strong>{' '}
              from {formatDateTime(new Date(pendingCancel.start_time + 'Z'))} to{' '}
              {formatDateTime(new Date(pendingCancel.end_time + 'Z'))}. This cannot be undone.
            </>
          )
        }
        confirmLabel="Cancel reservation"
        cancelLabel="Keep it"
        busy={cancelBusy}
        onConfirm={confirmCancel}
        onCancel={() => setPendingCancel(null)}
      />
    </div>
  )
}
