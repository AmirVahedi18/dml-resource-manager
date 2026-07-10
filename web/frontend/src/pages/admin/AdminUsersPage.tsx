import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBan, faCheck, faCircleCheck, faShieldHalved, faTrash, faUser } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminServersApi, adminUsersApi } from '../../api/endpoints'
import type { ServerAdminOut, UserAdminOut } from '../../api/types'
import { ServerAccessChips } from '../../components/ServerAccessChips'

interface Draft {
  username: string
  password: string
  full_name: string
  student_id: string
  max_concurrent_gpus: number
  server_ids: number[]
}

function emptyDraft(): Draft {
  return { username: '', password: '', full_name: '', student_id: '', max_concurrent_gpus: 1, server_ids: [] }
}

export function AdminUsersPage() {
  const [users, setUsers] = useState<UserAdminOut[] | null>(null)
  const [servers, setServers] = useState<ServerAdminOut[]>([])
  const [error, setError] = useState<string | null>(null)

  const [draft, setDraft] = useState<Draft>(emptyDraft())
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [maxGpusValue, setMaxGpusValue] = useState(1)
  const [accessSelection, setAccessSelection] = useState<number[]>([])
  const [newPassword, setNewPassword] = useState('')

  function reload() {
    adminUsersApi.list().then(setUsers).catch((e) => setError(errorMessage(e)))
    adminServersApi.list().then(setServers).catch((e) => setError(errorMessage(e)))
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
    setError(null)
    setCreateSuccess(null)
    if (!draft.username.trim() || !draft.password.trim() || !draft.full_name.trim()) {
      setError('Fill in username, password, and full name.')
      return
    }
    setBusy(true)
    try {
      const { results } = await adminUsersApi.bulkCreate([
        {
          username: draft.username.trim(),
          password: draft.password,
          full_name: draft.full_name.trim(),
          student_id: draft.student_id.trim() || null,
          max_concurrent_gpus: draft.max_concurrent_gpus,
          server_ids: draft.server_ids,
        },
      ])
      const result = results[0]
      if (result.success) {
        setDraft(emptyDraft())
        setCreateSuccess(`${result.username} created.`)
        reload()
      } else {
        setError(result.error ?? 'Failed to create user.')
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRename() {
    if (!selected) return
    try {
      await adminUsersApi.rename(selected.id, renameValue)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleToggleActive() {
    if (!selected) return
    try {
      await adminUsersApi.setActive(selected.id, !selected.is_active)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleToggleAdmin() {
    if (!selected) return
    try {
      await adminUsersApi.setAdmin(selected.id, !selected.is_admin)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleSetMaxGpus() {
    if (!selected) return
    try {
      await adminUsersApi.setMaxConcurrentGpus(selected.id, maxGpusValue)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleSetAccess() {
    if (!selected) return
    try {
      await adminUsersApi.setServerAccess(selected.id, accessSelection)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleResetPassword() {
    if (!selected || !newPassword) return
    try {
      await adminUsersApi.resetPassword(selected.id, newPassword)
      setNewPassword('')
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleDelete() {
    if (!selected) return
    if (!confirm(`Permanently delete ${selected.full_name} and all their reservations/watches? This cannot be undone.`)) return
    try {
      await adminUsersApi.delete(selected.id)
      setSelectedId(null)
      reload()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faUser} /> Manage Users
      </h1>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <h2>Add user</h2>
        <p className="muted">Set a username and password for the new account.</p>
        {createSuccess && (
          <div className="success-banner">
            <FontAwesomeIcon icon={faCircleCheck} /> {createSuccess}
          </div>
        )}
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
          <div className="field" style={{ minWidth: 100 }}>
            <label>Student ID</label>
            <input value={draft.student_id} onChange={(e) => updateDraft({ student_id: e.target.value })} />
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
        <div className="field" style={{ marginTop: 4 }}>
          <label>Server access</label>
          <ServerAccessChips servers={servers} selected={draft.server_ids} onToggle={toggleDraftServer} />
        </div>
        <button className="btn btn-primary" onClick={handleCreate} disabled={busy}>
          {busy ? 'Creating…' : 'Create user'}
        </button>
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
                  <th>Max GPUs</th>
                  <th>Servers</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.full_name}</td>
                    <td>{u.username}</td>
                    <td>
                      <span className={`badge ${u.is_active ? 'badge-success' : 'badge-neutral'}`}>
                        {u.is_active ? 'active' : 'inactive'}
                      </span>
                    </td>
                    <td>{u.is_admin && <span className="badge badge-warn">admin</span>}</td>
                    <td>{u.max_concurrent_gpus}</td>
                    <td>{u.server_ids.length}</td>
                    <td>
                      <button className="btn btn-sm" onClick={() => selectUser(u)}>
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <div className="card">
          <h2>{selected.full_name}</h2>
          <div className="row">
            <div className="field">
              <label>Rename</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} />
                <button className="btn btn-sm" onClick={handleRename}>
                  Save
                </button>
              </div>
            </div>
            <div className="field">
              <label>Max concurrent GPUs</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input type="number" min={1} value={maxGpusValue} onChange={(e) => setMaxGpusValue(Number(e.target.value))} />
                <button className="btn btn-sm" onClick={handleSetMaxGpus}>
                  Save
                </button>
              </div>
            </div>
            <div className="field">
              <label>Reset password</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" />
                <button className="btn btn-sm" onClick={handleResetPassword}>
                  Set
                </button>
              </div>
            </div>
          </div>

          <div className="field">
            <label>Server access</label>
            <ServerAccessChips
              servers={servers}
              selected={accessSelection}
              onToggle={(id) => setAccessSelection((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))}
            />
            <button className="btn btn-sm" style={{ marginTop: 10, width: 'fit-content' }} onClick={handleSetAccess}>
              Save access
            </button>
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn" onClick={handleToggleActive}>
              <FontAwesomeIcon icon={selected.is_active ? faBan : faCheck} />{' '}
              {selected.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <button className="btn" onClick={handleToggleAdmin}>
              <FontAwesomeIcon icon={faShieldHalved} /> {selected.is_admin ? 'Revoke admin' : 'Grant admin'}
            </button>
            <button className="btn btn-danger" onClick={handleDelete}>
              <FontAwesomeIcon icon={faTrash} /> Delete
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
