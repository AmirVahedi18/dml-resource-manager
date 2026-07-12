import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faComment, faTrash } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminFeedbackApi, adminUsersApi } from '../../api/endpoints'
import type { AdminFeedbackOut, FeedbackCategory, UserAdminOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Pagination } from '../../components/Pagination'
import { Select } from '../../components/Select'
import { useToast } from '../../components/Toast'
import { fadeSlideVariants, fadeVariants } from '../../motion'
import { formatDateTime } from '../../utils/formatDate'

const ALL_USERS = -1
const ALL_CATEGORIES = 'ALL'
const PAGE_SIZE = 25

const CATEGORY_OPTIONS: { value: FeedbackCategory | typeof ALL_CATEGORIES; label: string }[] = [
  { value: ALL_CATEGORIES, label: 'All categories' },
  { value: 'BUG', label: 'Bug' },
  { value: 'PROBLEM', label: 'Problem' },
  { value: 'SUGGESTION', label: 'Suggestion' },
  { value: 'OTHER', label: 'Other' },
]

const CATEGORY_BADGE: Record<FeedbackCategory, string> = {
  BUG: 'badge-danger',
  PROBLEM: 'badge-warn',
  SUGGESTION: 'badge-success',
  OTHER: 'badge-neutral',
}

export function AdminFeedbackPage() {
  const toast = useToast()
  const [users, setUsers] = useState<UserAdminOut[]>([])
  const [userId, setUserId] = useState<number>(ALL_USERS)
  const [category, setCategory] = useState<FeedbackCategory | typeof ALL_CATEGORIES>(ALL_CATEGORIES)
  const [feedback, setFeedback] = useState<AdminFeedbackOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const [pendingDelete, setPendingDelete] = useState<AdminFeedbackOut | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  useEffect(() => {
    adminUsersApi.list().then(setUsers).catch((e) => toast.error(errorMessage(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setPage(1)
  }, [userId, category])

  function reload() {
    adminFeedbackApi
      .list(
        userId === ALL_USERS ? undefined : userId,
        category === ALL_CATEGORIES ? undefined : category,
        page,
        PAGE_SIZE,
      )
      .then((r) => {
        setFeedback(r.items)
        setTotal(r.total)
      })
      .catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, category, page])

  async function confirmDelete() {
    if (!pendingDelete) return
    setDeleteBusy(true)
    try {
      await adminFeedbackApi.delete(pendingDelete.id)
      setPendingDelete(null)
      toast.success('Feedback deleted.')
      reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faComment} /> Feedback
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
          <div className="field" style={{ maxWidth: 220 }}>
            <label>Category</label>
            <Select value={category} options={CATEGORY_OPTIONS} onChange={setCategory} />
          </div>
        </div>

        <AnimatePresence>
          {feedback && (
            <motion.div className="table-scroll" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Category</th>
                    <th>Message</th>
                    <th>Submitted</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence>
                    {feedback.map((f) => (
                      <motion.tr key={f.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                        <td>{f.user_full_name}</td>
                        <td>
                          <span className={`badge ${CATEGORY_BADGE[f.category]}`}>{f.category}</span>
                        </td>
                        <td style={{ maxWidth: 420, whiteSpace: 'pre-wrap' }}>{f.message}</td>
                        <td className="num">{formatDateTime(new Date(f.created_at + 'Z'))}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-sm btn-danger" onClick={() => setPendingDelete(f)}>
                            <FontAwesomeIcon icon={faTrash} /> Delete
                          </button>
                        </td>
                      </motion.tr>
                    ))}
                    {feedback.length === 0 && (
                      <motion.tr key="empty" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                        <td colSpan={5} className="muted">
                          No feedback submitted yet.
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
        open={pendingDelete !== null}
        title="Delete feedback?"
        message={
          pendingDelete && (
            <>
              Permanently delete <strong>{pendingDelete.user_full_name}</strong>'s feedback? This cannot be undone.
            </>
          )
        }
        confirmLabel="Delete"
        cancelLabel="Keep it"
        busy={deleteBusy}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}
