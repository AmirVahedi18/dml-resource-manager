import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBell, faCalendarDays } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../api/errorMessage'
import { reservationsApi, watchesApi } from '../api/endpoints'
import type { ReservationOut, WatchOut } from '../api/types'
import { useGpuLookup } from '../api/useGpuLookup'
import { formatDateTime } from '../utils/formatDate'
import { ConfirmDialog } from './ConfirmDialog'
import { fadeSlideVariants, fadeVariants } from '../motion'
import { useToast } from './Toast'

/**
 * `reloadSignal` — bump this number (from a parent) to force the list to refetch, e.g.
 * after the parent creates a reservation. Without it, this card kept its own state and
 * went stale when a booking was made elsewhere on the page.
 */
export function MyReservationsCard({ reloadSignal = 0 }: { reloadSignal?: number }) {
  const [reservations, setReservations] = useState<ReservationOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const gpuLookup = useGpuLookup()
  const toast = useToast()

  const [pendingCancel, setPendingCancel] = useState<ReservationOut | null>(null)
  const [cancelBusy, setCancelBusy] = useState(false)

  const [watches, setWatches] = useState<WatchOut[] | null>(null)

  function reload() {
    reservationsApi.list(true).then(setReservations).catch((e) => {
      const msg = errorMessage(e)
      setError(msg)
      toast.error(msg)
    })
  }

  function reloadWatches() {
    watchesApi.list().then(setWatches).catch((e) => toast.error(errorMessage(e)))
  }

  // Refetch on mount and whenever the parent bumps reloadSignal (e.g. after a booking or watch).
  useEffect(reload, [reloadSignal])
  useEffect(reloadWatches, [reloadSignal])

  async function handleCancelWatch(id: number) {
    try {
      await watchesApi.cancel(id)
      reloadWatches()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function confirmCancel() {
    if (!pendingCancel) return
    setCancelBusy(true)
    try {
      await reservationsApi.cancel(pendingCancel.id)
      setPendingCancel(null)
      reload()
      toast.success('Reservation cancelled.')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  return (
    <div className="card">
      <h2>
        <FontAwesomeIcon icon={faCalendarDays} /> My Reservations
      </h2>
      <AnimatePresence mode="wait">
        {reservations === null && !error && (
          <motion.div key="skeleton" aria-hidden variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            <div className="skeleton-line" style={{ width: '70%' }} />
            <div className="skeleton-line" style={{ width: '85%' }} />
            <div className="skeleton-line" style={{ width: '60%' }} />
          </motion.div>
        )}
        {reservations?.length === 0 && (
          <motion.div key="empty" className="empty-state" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            <FontAwesomeIcon icon={faCalendarDays} className="empty-state-icon" />
            <p className="empty-state-title">No upcoming reservations</p>
            <p className="muted">Book your first GPU using the form below.</p>
          </motion.div>
        )}
        {reservations && reservations.length > 0 && (
          <motion.div key="list" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            <div className="table-scroll reservation-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>GPU</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>RAM</th>
                    <th className="table-actions" />
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence>
                    {reservations.map((r) => {
                      const gpu = gpuLookup[r.gpu_id]
                      return (
                        <motion.tr key={r.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                          <td>{gpu ? `${gpu.serverName} GPU${gpu.indexOnServer}` : `GPU #${r.gpu_id}`}</td>
                          {/* time/RAM cells use the .num (Ubuntu Mono) style for aligned digits */}
                          <td className="num">{formatDateTime(new Date(r.start_time + 'Z'))}</td>
                          <td className="num">{formatDateTime(new Date(r.end_time + 'Z'))}</td>
                          <td className="num">{(r.ram_mb / 1024).toFixed(1)} GB</td>
                          <td className="table-actions">
                            <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(r)}>
                              Cancel
                            </button>
                          </td>
                        </motion.tr>
                      )
                    })}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>

            <div className="reservation-cards">
              <AnimatePresence>
                {reservations.map((r) => {
                  const gpu = gpuLookup[r.gpu_id]
                  return (
                    <motion.div
                      className="reservation-card"
                      key={r.id}
                      layout
                      variants={fadeSlideVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                    >
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
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <h2 style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
        <FontAwesomeIcon icon={faBell} /> My Watches
      </h2>
      <AnimatePresence mode="wait">
        {watches?.length === 0 && (
          <motion.p key="empty" className="muted" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            No active watches.
          </motion.p>
        )}
        {watches && watches.length > 0 && (
          <motion.div key="list" className="table-scroll" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
            <table>
              <thead>
                <tr>
                  <th>GPU</th>
                  <th>From</th>
                  <th>Until</th>
                  <th>Min RAM</th>
                  <th className="table-actions" />
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {watches.map((w) => {
                    const gpu = gpuLookup[w.gpu_id]
                    return (
                      <motion.tr key={w.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                        <td>{gpu ? `${gpu.serverName} GPU${gpu.indexOnServer}` : `GPU #${w.gpu_id}`}</td>
                        <td className="num">{formatDateTime(new Date(w.range_start + 'Z'))}</td>
                        <td className="num">{formatDateTime(new Date(w.range_end + 'Z'))}</td>
                        <td className="num">{(w.min_ram_needed_mb / 1024).toFixed(1)} GB</td>
                        <td className="table-actions">
                          <button className="btn btn-sm btn-danger" onClick={() => handleCancelWatch(w.id)}>
                            Cancel
                          </button>
                        </td>
                      </motion.tr>
                    )
                  })}
                </AnimatePresence>
              </tbody>
            </table>
          </motion.div>
        )}
      </AnimatePresence>

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
