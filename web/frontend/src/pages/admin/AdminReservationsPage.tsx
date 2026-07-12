import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faClipboardList, faTrash } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminReservationsApi, adminServersApi, adminUsersApi } from '../../api/endpoints'
import type { AdminReservationOut, GpuAdminOut, ServerAdminOut, UserAdminOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Pagination } from '../../components/Pagination'
import { Select } from '../../components/Select'
import { useToast } from '../../components/Toast'
import { fadeSlideVariants, fadeVariants } from '../../motion'
import { formatDateTime } from '../../utils/formatDate'

const CONFIRM_PHRASE = 'CANCEL ALL'
const ALL_USERS = -1
const ALL_SERVERS = -1
const ALL_GPUS = -1
const PAGE_SIZE = 25

export function AdminReservationsPage() {
  const toast = useToast()
  const [users, setUsers] = useState<UserAdminOut[]>([])
  const [userId, setUserId] = useState<number>(ALL_USERS)
  const [servers, setServers] = useState<ServerAdminOut[]>([])
  const [serverId, setServerId] = useState<number>(ALL_SERVERS)
  const [gpus, setGpus] = useState<GpuAdminOut[]>([])
  const [gpuId, setGpuId] = useState<number>(ALL_GPUS)
  const [reservations, setReservations] = useState<AdminReservationOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [confirmText, setConfirmText] = useState('')

  const [pendingCancel, setPendingCancel] = useState<AdminReservationOut | null>(null)
  const [pendingCancelForUser, setPendingCancelForUser] = useState(false)
  const [cancelBusy, setCancelBusy] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  useEffect(() => {
    adminUsersApi.list().then(setUsers).catch((e) => toast.error(errorMessage(e)))
    adminServersApi.list().then(setServers).catch((e) => toast.error(errorMessage(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Reset the GPU filter whenever the server filter changes, and load that server's GPUs.
  useEffect(() => {
    setGpuId(ALL_GPUS)
    if (serverId === ALL_SERVERS) {
      setGpus([])
      return
    }
    adminServersApi.gpus(serverId).then(setGpus).catch((e) => toast.error(errorMessage(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverId])

  // Any filter change invalidates the current page -- start back at page 1.
  useEffect(() => {
    setPage(1)
  }, [userId, serverId, gpuId])

  function reload() {
    adminReservationsApi
      .list(
        userId === ALL_USERS ? undefined : userId,
        gpuId === ALL_GPUS ? undefined : gpuId,
        serverId === ALL_SERVERS ? undefined : serverId,
        page,
        PAGE_SIZE,
      )
      .then((r) => {
        setReservations(r.items)
        setTotal(r.total)
      })
      .catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, serverId, gpuId, page])

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
        <div className="row row-tight">
          <div className="field" style={{ maxWidth: 260 }}>
            <label>Student</label>
            <Select
              value={userId}
              options={[{ value: ALL_USERS, label: 'All students' }, ...users.map((u) => ({ value: u.id, label: u.full_name }))]}
              onChange={setUserId}
            />
          </div>
          <div className="field" style={{ maxWidth: 260 }}>
            <label>Server</label>
            <Select
              value={serverId}
              options={[{ value: ALL_SERVERS, label: 'All servers' }, ...servers.map((s) => ({ value: s.id, label: s.name }))]}
              onChange={setServerId}
            />
          </div>
          <div className="field" style={{ maxWidth: 260 }}>
            <label>GPU</label>
            <Select
              value={gpuId}
              disabled={serverId === ALL_SERVERS}
              options={[
                { value: ALL_GPUS, label: 'All GPUs' },
                ...gpus.map((g) => ({ value: g.id, label: `GPU${g.index_on_server} (${g.model_name})` })),
              ]}
              onChange={setGpuId}
            />
          </div>
        </div>

        <AnimatePresence>
          {reservations && (
            <motion.div className="table-scroll" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>GPU</th>
                    <th>Description</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>RAM</th>
                    <th>Status</th>
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
                        <td className="muted">{r.description || '—'}</td>
                        <td>{formatDateTime(new Date(r.start_time + 'Z'))}</td>
                        <td>{formatDateTime(new Date(r.end_time + 'Z'))}</td>
                        <td>{(r.ram_mb / 1024).toFixed(1)} GB</td>
                        <td>
                          {r.status === 'SUSPENDED' && (
                            <span className="badge badge-warn" title="Its GPU/server is deactivated; this will resume automatically once it's reactivated.">
                              Suspended
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(r)}>
                            Cancel
                          </button>
                        </td>
                      </motion.tr>
                    ))}
                    {reservations.length === 0 && (
                      <motion.tr key="empty" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                        <td colSpan={8} className="muted">
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

        <Pagination
          page={page}
          totalPages={totalPages}
          onChange={setPage}
          rangeLabel={total > 0 ? `Showing ${(page - 1) * PAGE_SIZE + 1}-${Math.min(page * PAGE_SIZE, total)} of ${total}` : undefined}
        />

        <AnimatePresence>
          {userId !== ALL_USERS && total > 0 && (
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
        {userId === ALL_USERS && total > 0 && (
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
              <button className="btn btn-danger" disabled={confirmText.trim() !== CONFIRM_PHRASE} onClick={handleCancelAll}>
                Cancel all
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
