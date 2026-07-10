import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBan, faCheck, faShieldHalved, faTrash, faUser } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminServersApi, adminUsersApi } from '../../api/endpoints'
import type { ServerAdminOut, UserAdminOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ServerAccessChips } from '../../components/ServerAccessChips'
import { useToast } from '../../components/Toast'
import { fadeSlideVariants } from '../../motion'

interface Draft {
  username: string
  password: string
  full_name: string
  max_concurrent_gpus: number
  server_ids: number[]
}

function emptyDraft(): Draft {
  return { username: '', password: '', full_name: '', max_concurrent_gpus: 1, server_ids: [] }
}

function sameServerIds(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false
  const bSet = new Set(b)
  return a.every((id) => bSet.has(id))
}

export function AdminUsersPage() {
  const toast = useToast()
  const [users, setUsers] = useState<UserAdminOut[] | null>(null)
  const [servers, setServers] = useState<ServerAdminOut[]>([])

  const [draft, setDraft] = useState<Draft>(emptyDraft())
  const [busy, setBusy] = useState(false)

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [maxGpusValue, setMaxGpusValue] = useState(1)
  const [accessSelection, setAccessSelection] = useState<number[]>([])
  const [newPassword, setNewPassword] = useState('')
  const [detailsBusy, setDetailsBusy] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(false)
  const [deleteBusy, setDeleteBusy] = useState(false)

  function reload() {
    adminUsersApi.list().then(setUsers).catch((e) => toast.error(errorMessage(e)))
    adminServersApi.list().then(setServers).catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(reload, [])

  const selected = users?.find((u) => u.id === selectedId) ?? null

  function selectUser(u: UserAdminOut) {
    setSelectedId(u.id)
    setRenameValue(u.full_name)
    setMaxGpusValue(u.max_concurrent_gpus)
    setAccessSelection(u.server_ids)
    setNewPassword('')
  }

  function updateDraft(patch: Partial<Draft>) {
    setDraft((prev) => ({ ...prev, ...patch }))
  }

  function toggleDraftServer(serverId: number) {
    setDraft((prev) => {
      const has = prev.server_ids.includes(serverId)
      return { ...prev, server_ids: has ? prev.server_ids.filter((id) => id !== serverId) : [...prev.server_ids, serverId] }
    })
  }

  async function handleCreate() {
    if (!draft.username.trim() || !draft.password.trim() || !draft.full_name.trim()) {
      toast.error('Fill in username, password, and full name.')
      return
    }
    setBusy(true)
    try {
      const { results } = await adminUsersApi.bulkCreate([
        {
          username: draft.username.trim(),
          password: draft.password,
          full_name: draft.full_name.trim(),
          max_concurrent_gpus: draft.max_concurrent_gpus,
          server_ids: draft.server_ids,
        },
      ])
      const result = results[0]
      if (result.success) {
        setDraft(emptyDraft())
        toast.success(`${result.username} created.`)
        reload()
      } else {
        toast.error(result.error ?? 'Failed to create user.')
      }
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveDetails() {
    if (!selected) return

    const tasks: Promise<unknown>[] = []
    if (renameValue.trim() && renameValue.trim() !== selected.full_name) {
      tasks.push(adminUsersApi.rename(selected.id, renameValue.trim()))
    }
    if (maxGpusValue !== selected.max_concurrent_gpus) {
      tasks.push(adminUsersApi.setMaxConcurrentGpus(selected.id, maxGpusValue))
    }
    if (newPassword) {
      tasks.push(adminUsersApi.resetPassword(selected.id, newPassword))
    }
    if (!sameServerIds(accessSelection, selected.server_ids)) {
      tasks.push(adminUsersApi.setServerAccess(selected.id, accessSelection))
    }

    if (tasks.length === 0) {
      toast.info('Nothing to save.')
      return
    }

    setDetailsBusy(true)
    try {
      await Promise.all(tasks)
      setNewPassword('')
      toast.success('Changes saved.')
      reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDetailsBusy(false)
    }
  }

  async function handleToggleActive() {
    if (!selected) return
    const nextActive = !selected.is_active
    try {
      await adminUsersApi.setActive(selected.id, nextActive)
      toast.success(`${selected.full_name} ${nextActive ? 'activated' : 'deactivated'}.`)
      reload()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleToggleAdmin() {
    if (!selected) return
    const nextAdmin = !selected.is_admin
    try {
      await adminUsersApi.setAdmin(selected.id, nextAdmin)
      toast.success(`${selected.full_name} ${nextAdmin ? 'granted' : 'revoked'} admin.`)
      reload()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleDelete() {
    if (!selected) return
    setDeleteBusy(true)
    try {
      await adminUsersApi.delete(selected.id)
      setPendingDelete(false)
      setSelectedId(null)
      toast.success(`${selected.full_name} deleted.`)
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
        <FontAwesomeIcon icon={faUser} /> Manage Users
      </h1>

      <div className="card">
        <h2>Add user</h2>
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <div className="field" style={{ minWidth: 120 }}>
            <label>Username</label>
            <input value={draft.username} onChange={(e) => updateDraft({ username: e.target.value })} />
          </div>
          <div className="field" style={{ minWidth: 120 }}>
            <label>Password</label>
            <input value={draft.password} onChange={(e) => updateDraft({ password: e.target.value })} />
          </div>
          <div className="field" style={{ minWidth: 140 }}>
            <label>Full name</label>
            <input value={draft.full_name} onChange={(e) => updateDraft({ full_name: e.target.value })} />
          </div>
          <div className="field" style={{ maxWidth: 90 }}>
            <label>Max GPUs</label>
            <input
              type="number"
              min={1}
              value={draft.max_concurrent_gpus}
              onChange={(e) => updateDraft({ max_concurrent_gpus: Number(e.target.value) })}
            />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 4 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Server access</label>
            <ServerAccessChips servers={servers} selected={draft.server_ids} onToggle={toggleDraftServer} />
          </div>
          <button className="btn btn-primary" onClick={handleCreate} disabled={busy}>
            {busy ? 'Creating…' : 'Create user'}
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Registered users</h2>
        {users && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Username</th>
                  <th>Status</th>
                  <th>Admin</th>
                  <th style={{ textAlign: 'center' }}>Max GPUs</th>
                  <th style={{ textAlign: 'center' }}>Servers</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {users.map((u) => (
                    <motion.tr key={u.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                      <td>{u.full_name}</td>
                      <td>{u.username ?? <span className="muted">deleted</span>}</td>
                      <td>
                        <span className={`badge ${u.is_active ? 'badge-success' : 'badge-neutral'}`}>
                          {u.is_active ? 'active' : 'inactive'}
                        </span>
                      </td>
                      <td>{u.is_admin && <span className="badge badge-warn">admin</span>}</td>
                      <td style={{ textAlign: 'center' }}>{u.max_concurrent_gpus}</td>
                      <td style={{ textAlign: 'center' }}>{u.server_ids.length}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-sm" onClick={() => selectUser(u)}>
                          Manage
                        </button>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </div>

      <AnimatePresence>
      {selected && (
        <motion.div className="card" variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
          <h2>{selected.full_name}</h2>
          <div className="row">
            <div className="field">
              <label>Rename</label>
              <input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} />
            </div>
            <div className="field">
              <label>Max concurrent GPUs</label>
              <input type="number" min={1} value={maxGpusValue} onChange={(e) => setMaxGpusValue(Number(e.target.value))} />
            </div>
            <div className="field">
              <label>Reset password</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Server access</label>
              <ServerAccessChips
                servers={servers}
                selected={accessSelection}
                onToggle={(id) => setAccessSelection((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={handleSaveDetails} disabled={detailsBusy}>
                {detailsBusy ? 'Saving…' : 'Save changes'}
              </button>
              <button className="btn" onClick={handleToggleActive}>
                <FontAwesomeIcon icon={selected.is_active ? faBan : faCheck} />{' '}
                {selected.is_active ? 'Deactivate' : 'Activate'}
              </button>
              <button className="btn" onClick={handleToggleAdmin}>
                <FontAwesomeIcon icon={faShieldHalved} /> {selected.is_admin ? 'Revoke admin' : 'Grant admin'}
              </button>
              <button className="btn btn-danger" onClick={() => setPendingDelete(true)}>
                <FontAwesomeIcon icon={faTrash} /> Delete
              </button>
            </div>
          </div>
        </motion.div>
      )}
      </AnimatePresence>

      <ConfirmDialog
        open={pendingDelete}
        title="Delete user?"
        message={
          selected && (
            <>
              Delete <strong>{selected.full_name}</strong>'s account? This revokes their login, admin role, watches,
              and server access. Their reservation history is kept for reporting. This cannot be undone.
            </>
          )
        }
        confirmLabel="Delete"
        busy={deleteBusy}
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(false)}
      />
    </div>
  )
}
