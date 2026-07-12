import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faEye } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminServersApi, adminUsersApi, adminWatchesApi } from '../../api/endpoints'
import type { AdminWatchOut, GpuAdminOut, ServerAdminOut, UserAdminOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Pagination } from '../../components/Pagination'
import { Select } from '../../components/Select'
import { useToast } from '../../components/Toast'
import { fadeSlideVariants, fadeVariants } from '../../motion'
import { formatDateTime } from '../../utils/formatDate'

const ALL_USERS = -1
const ALL_SERVERS = -1
const ALL_GPUS = -1
const PAGE_SIZE = 25

const STATUS_LABELS: Record<string, string> = {
  active: 'Watching',
  matched: 'Matched',
  cancelled: 'Cancelled',
}

const STATUS_BADGE_CLASS: Record<string, string> = {
  active: 'badge-warn',
  matched: 'badge-success',
  cancelled: 'badge-neutral',
}

export function AdminWatchesPage() {
  const toast = useToast()
  const [users, setUsers] = useState<UserAdminOut[]>([])
  const [userId, setUserId] = useState<number>(ALL_USERS)
  const [servers, setServers] = useState<ServerAdminOut[]>([])
  const [serverId, setServerId] = useState<number>(ALL_SERVERS)
  const [gpus, setGpus] = useState<GpuAdminOut[]>([])
  const [gpuId, setGpuId] = useState<number>(ALL_GPUS)
  const [watches, setWatches] = useState<AdminWatchOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const [pendingCancel, setPendingCancel] = useState<AdminWatchOut | null>(null)
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
    adminWatchesApi
      .list(
        userId === ALL_USERS ? undefined : userId,
        gpuId === ALL_GPUS ? undefined : gpuId,
        serverId === ALL_SERVERS ? undefined : serverId,
        page,
        PAGE_SIZE,
      )
      .then((r) => {
        setWatches(r.items)
        setTotal(r.total)
      })
      .catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, serverId, gpuId, page])

  async function confirmCancelWatch() {
    if (!pendingCancel) return
    setCancelBusy(true)
    try {
      await adminWatchesApi.cancel(pendingCancel.id)
      setPendingCancel(null)
      reload()
      toast.success('Watch cancelled.')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setCancelBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faEye} /> All Watches
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
          {watches && (
            <motion.div className="table-scroll" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>GPU</th>
                    <th>Description</th>
                    <th>Range</th>
                    <th>Min RAM</th>
                    <th>Auto-book</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence>
                    {watches.map((w) => (
                      <motion.tr key={w.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                        <td>{w.user_full_name}</td>
                        <td>
                          {w.server_name} GPU{w.gpu_index}
                        </td>
                        <td className="muted">{w.description || '—'}</td>
                        <td>
                          {formatDateTime(new Date(w.range_start + 'Z'))} –{' '}
                          {formatDateTime(new Date(w.range_end + 'Z'))}
                        </td>
                        <td>{(w.min_ram_needed_mb / 1024).toFixed(1)} GB</td>
                        <td>{w.auto_book ? 'Yes' : 'No'}</td>
                        <td>
                          <span className={`badge ${STATUS_BADGE_CLASS[w.status] ?? 'badge-neutral'}`}>
                            {STATUS_LABELS[w.status] ?? w.status}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          {w.status === 'active' && (
                            <button className="btn btn-sm btn-danger" onClick={() => setPendingCancel(w)}>
                              Cancel
                            </button>
                          )}
                        </td>
                      </motion.tr>
                    ))}
                    {watches.length === 0 && (
                      <motion.tr key="empty" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                        <td colSpan={8} className="muted">
                          No watches yet.
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
      </div>

      <ConfirmDialog
        open={pendingCancel !== null}
        title="Cancel watch?"
        message={
          pendingCancel && (
            <>
              This will cancel <strong>{pendingCancel.user_full_name}</strong>'s watch on{' '}
              <strong>
                {pendingCancel.server_name} GPU{pendingCancel.gpu_index}
              </strong>{' '}
              for {formatDateTime(new Date(pendingCancel.range_start + 'Z'))} to{' '}
              {formatDateTime(new Date(pendingCancel.range_end + 'Z'))}. This cannot be undone.
            </>
          )
        }
        confirmLabel="Cancel watch"
        cancelLabel="Keep it"
        busy={cancelBusy}
        onConfirm={confirmCancelWatch}
        onCancel={() => setPendingCancel(null)}
      />
    </div>
  )
}
