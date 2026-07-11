import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faClipboardList, faTrash } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminReservationsApi } from '../../api/endpoints'
import type { AdminReservationOut, UserWithReservationsOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Select } from '../../components/Select'
import { useToast } from '../../components/Toast'
import { fadeSlideVariants, fadeVariants } from '../../motion'
import { formatDateTime } from '../../utils/formatDate'

const CONFIRM_PHRASE = 'CANCEL ALL'
const ALL_USERS = -1

export function AdminReservationsPage() {
  const toast = useToast()
  const [users, setUsers] = useState<UserWithReservationsOut[]>([])
  const [userId, setUserId] = useState<number>(ALL_USERS)
  const [reservations, setReservations] = useState<AdminReservationOut[] | null>(null)
  const [confirmText, setConfirmText] = useState('')

  const [pendingCancel, setPendingCancel] = useState<AdminReservationOut | null>(null)
  const [pendingCancelForUser, setPendingCancelForUser] = useState(false)
  const [cancelBusy, setCancelBusy] = useState(false)

  useEffect(() => {
    adminReservationsApi.usersWithReservations().then(setUsers).catch((e) => toast.error(errorMessage(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function reload() {
    adminReservationsApi
      .list(userId === ALL_USERS ? undefined : userId)
      .then(setReservations)
      .catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  async function confirmCancelReservation() {
    if (!pendingCancel) return
    setCancelBusy(true)
    try {
      await adminReservationsApi.cancel(pendingCancel.id)
      setPendingCancel(null)
      reload()
      toast.success('Reservation cancelled.')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  async function confirmCancelForUser() {
    if (userId === ALL_USERS) return
    setCancelBusy(true)
    try {
      const { cancelled } = await adminReservationsApi.cancelForUser(userId)
      setPendingCancelForUser(false)
      toast.success(`Cancelled ${cancelled} reservation(s).`)
      reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  async function handleCancelAll() {
    try {
      const { cancelled } = await adminReservationsApi.cancelAll(confirmText)
      toast.success(`Cancelled ${cancelled} reservation(s) lab-wide.`)
      setConfirmText('')
      reload()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faClipboardList} /> All Reservations
      </h1>

      <div className="card">
        <div className="field" style={{ maxWidth: 260 }}>
          <label>Student</label>
          <Select
            value={userId}
            options={[{ value: ALL_USERS, label: 'All students' }, ...users.map((u) => ({ value: u.id, label: u.full_name }))]}
            onChange={setUserId}
          />
        </div>

        <AnimatePresence>
          {reservations && (
            <motion.div className="table-scroll" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
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
                  <AnimatePresence>
                    {reservations.map((r) => (
                      <motion.tr key={r.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                        <td>{r.user_full_name}</td>
                        <td>
                          {r.server_name} GPU{r.gpu_index}
                        </td>
                        <td>{formatDateTime(new Date(r.start_time + 'Z'))}</td>
                        <td>{formatDateTime(new Date(r.end_time + 'Z'))}</td>
                        <td>{(r.ram_mb / 1024).toFixed(1)} GB</td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(r)}>
                            Cancel
                          </button>
                        </td>
                      </motion.tr>
                    ))}
                    {reservations.length === 0 && (
                      <motion.tr key="empty" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                        <td colSpan={6} className="muted">
                          No upcoming reservations.
                        </td>
                      </motion.tr>
                    )}
                  </AnimatePresence>
                </tbody>
              </table>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {userId !== ALL_USERS && (reservations?.length ?? 0) > 0 && (
            <motion.div
              style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}
              variants={fadeSlideVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <button className="btn btn-danger" onClick={() => setPendingCancelForUser(true)}>
                <FontAwesomeIcon icon={faTrash} /> Cancel All (this user)
              </button>
            </motion.div>
          )}
        </AnimatePresence>
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

      <AnimatePresence>
        {userId === ALL_USERS && (reservations?.length ?? 0) > 0 && (
          <motion.div className="card" variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
            <h2>
              <FontAwesomeIcon icon={faTrash} /> Cancel ALL Reservations lab-wide
            </h2>
            <p className="muted">This cannot be undone. Type "{CONFIRM_PHRASE}" to confirm.</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'space-between' }}>
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
