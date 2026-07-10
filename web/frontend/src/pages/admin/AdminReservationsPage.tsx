import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faClipboardList, faFolderOpen, faTrash, faUser } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminReservationsApi } from '../../api/endpoints'
import type { AdminReservationOut, UserWithReservationsOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Select } from '../../components/Select'
import { formatDateTime } from '../../utils/formatDate'

const CONFIRM_PHRASE = 'CANCEL ALL'

export function AdminReservationsPage() {
  const [scope, setScope] = useState<'all' | 'user'>('all')
  const [users, setUsers] = useState<UserWithReservationsOut[]>([])
  const [userId, setUserId] = useState<number | null>(null)
  const [reservations, setReservations] = useState<AdminReservationOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmText, setConfirmText] = useState('')

  const [pendingCancel, setPendingCancel] = useState<AdminReservationOut | null>(null)
  const [pendingCancelForUser, setPendingCancelForUser] = useState(false)
  const [cancelBusy, setCancelBusy] = useState(false)

  useEffect(() => {
    adminReservationsApi.usersWithReservations().then(setUsers).catch((e) => setError(errorMessage(e)))
  }, [])

  function reload() {
    adminReservationsApi
      .list(scope === 'user' && userId ? userId : undefined)
      .then(setReservations)
      .catch((e) => setError(errorMessage(e)))
  }

  useEffect(() => {
    if (scope === 'all' || userId) reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, userId])

  async function confirmCancelReservation() {
    if (!pendingCancel) return
    setError(null)
    setCancelBusy(true)
    try {
      await adminReservationsApi.cancel(pendingCancel.id)
      setPendingCancel(null)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  async function confirmCancelForUser() {
    if (!userId) return
    setError(null)
    setCancelBusy(true)
    try {
      const { cancelled } = await adminReservationsApi.cancelForUser(userId)
      setPendingCancelForUser(false)
      alert(`Cancelled ${cancelled} reservation(s).`)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  async function handleCancelAll() {
    try {
      const { cancelled } = await adminReservationsApi.cancelAll(confirmText)
      alert(`Cancelled ${cancelled} reservation(s) lab-wide.`)
      setConfirmText('')
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faClipboardList} /> All Reservations
      </h1>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <div className="tabs" role="tablist" aria-label="Reservation scope">
          <button
            type="button"
            role="tab"
            aria-selected={scope === 'all'}
            className={`tab${scope === 'all' ? ' active' : ''}`}
            onClick={() => setScope('all')}
          >
            <FontAwesomeIcon icon={faFolderOpen} /> All Reservations
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={scope === 'user'}
            className={`tab${scope === 'user' ? ' active' : ''}`}
            onClick={() => setScope('user')}
          >
            <FontAwesomeIcon icon={faUser} /> By User
          </button>
        </div>

        {scope === 'user' && (
          <div className="field" style={{ maxWidth: 260 }}>
            <label>Student</label>
            <Select
              value={userId}
              placeholder="Select a student…"
              options={users.map((u) => ({ value: u.id, label: u.full_name }))}
              onChange={setUserId}
            />
          </div>
        )}

        {reservations && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>GPU</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>RAM</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {reservations.map((r) => (
                  <tr key={r.id}>
                    <td>{r.user_full_name}</td>
                    <td>
                      {r.server_name} GPU{r.gpu_index}
                    </td>
                    <td>{formatDateTime(new Date(r.start_time + 'Z'))}</td>
                    <td>{formatDateTime(new Date(r.end_time + 'Z'))}</td>
                    <td>{(r.ram_mb / 1024).toFixed(1)} GB</td>
                    <td>
                      <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(r)}>
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
                {reservations.length === 0 && (
                  <tr>
                    <td colSpan={6} className="muted">
                      No upcoming reservations.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {scope === 'user' && userId && (reservations?.length ?? 0) > 0 && (
          <button className="btn btn-danger" style={{ marginTop: 12 }} onClick={() => setPendingCancelForUser(true)}>
            <FontAwesomeIcon icon={faTrash} /> Cancel All (this user)
          </button>
        )}
      </div>

      <ConfirmDialog
        open={pendingCancel !== null}
        title="Cancel reservation?"
        message={
          pendingCancel && (
            <>
              This will cancel <strong>{pendingCancel.user_full_name}</strong>'s reservation on{' '}
              <strong>
                {pendingCancel.server_name} GPU{pendingCancel.gpu_index}
              </strong>{' '}
              from {formatDateTime(new Date(pendingCancel.start_time + 'Z'))} to{' '}
              {formatDateTime(new Date(pendingCancel.end_time + 'Z'))}. This cannot be undone.
            </>
          )
        }
        confirmLabel="Cancel reservation"
        cancelLabel="Keep it"
        busy={cancelBusy}
        onConfirm={confirmCancelReservation}
        onCancel={() => setPendingCancel(null)}
      />

      <ConfirmDialog
        open={pendingCancelForUser}
        title="Cancel all reservations for this student?"
        message="This cancels every upcoming reservation for this student. This cannot be undone."
        confirmLabel="Cancel all"
        cancelLabel="Keep them"
        busy={cancelBusy}
        onConfirm={confirmCancelForUser}
        onCancel={() => setPendingCancelForUser(false)}
      />

      {scope === 'all' && (reservations?.length ?? 0) > 0 && (
        <div className="card">
          <h2>
            <FontAwesomeIcon icon={faTrash} /> Cancel ALL Reservations lab-wide
          </h2>
          <p className="muted">This cannot be undone. Type "{CONFIRM_PHRASE}" to confirm.</p>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className="text-input"
              style={{ maxWidth: 220 }}
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={CONFIRM_PHRASE}
            />
            <button className="btn btn-danger" disabled={confirmText.trim().toUpperCase() !== CONFIRM_PHRASE} onClick={handleCancelAll}>
              Cancel all
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
