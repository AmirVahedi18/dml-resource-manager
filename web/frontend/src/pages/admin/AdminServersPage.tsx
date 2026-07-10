import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBan, faCheck, faServer, faTrash } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminServersApi } from '../../api/endpoints'
import type { GpuAdminOut, ServerAdminOut } from '../../api/types'

export function AdminServersPage() {
  const [servers, setServers] = useState<ServerAdminOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [newServerName, setNewServerName] = useState('')
  const [newServerDesc, setNewServerDesc] = useState('')

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [gpus, setGpus] = useState<GpuAdminOut[]>([])

  const [gpuIndex, setGpuIndex] = useState(0)
  const [gpuModel, setGpuModel] = useState('')
  const [gpuRam, setGpuRam] = useState(24)

  function reloadServers() {
    adminServersApi.list().then(setServers).catch((e) => setError(errorMessage(e)))
  }

  useEffect(reloadServers, [])

  const selected = servers?.find((s) => s.id === selectedId) ?? null

  function selectServer(s: ServerAdminOut) {
    setSelectedId(s.id)
    setRenameValue(s.name)
    adminServersApi.gpus(s.id).then(setGpus).catch((e) => setError(errorMessage(e)))
  }

  async function handleCreateServer() {
    if (!newServerName.trim()) return
    try {
      await adminServersApi.create(newServerName.trim(), newServerDesc.trim() || undefined)
      setNewServerName('')
      setNewServerDesc('')
      reloadServers()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleRename() {
    if (!selected) return
    try {
      await adminServersApi.rename(selected.id, renameValue)
      reloadServers()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleToggleActive() {
    if (!selected) return
    try {
      await adminServersApi.setActive(selected.id, !selected.is_active)
      reloadServers()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleDeleteServer() {
    if (!selected) return
    if (!confirm(`Permanently delete ${selected.name} and all its GPUs/reservations/watches? This cannot be undone.`)) return
    try {
      await adminServersApi.delete(selected.id)
      setSelectedId(null)
      reloadServers()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleAddGpu() {
    if (!selected || !gpuModel.trim()) return
    try {
      await adminServersApi.addGpu(selected.id, gpuIndex, gpuModel.trim(), Math.round(gpuRam * 1024))
      setGpuModel('')
      adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleToggleGpuActive(g: GpuAdminOut) {
    try {
      await adminServersApi.setGpuActive(g.id, !g.is_active)
      if (selected) adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleRenameGpu(g: GpuAdminOut) {
    const modelName = prompt('New model name', g.model_name)
    if (!modelName) return
    try {
      await adminServersApi.renameGpu(g.id, modelName)
      if (selected) adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  async function handleDeleteGpu(g: GpuAdminOut) {
    if (!confirm(`Permanently delete GPU${g.index_on_server} and all its reservations/watches?`)) return
    try {
      await adminServersApi.deleteGpu(g.id)
      if (selected) adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faServer} /> Manage Servers
      </h1>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <h2>Add server</h2>
        <div className="row">
          <div className="field">
            <label>Name</label>
            <input value={newServerName} onChange={(e) => setNewServerName(e.target.value)} />
          </div>
          <div className="field">
            <label>Description</label>
            <input value={newServerDesc} onChange={(e) => setNewServerDesc(e.target.value)} />
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleCreateServer}>
          Add server
        </button>
      </div>

      <div className="card">
        <h2>Servers</h2>
        {servers && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {servers.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name}</td>
                    <td className="muted">{s.description}</td>
                    <td>
                      <span className={`badge ${s.is_active ? 'badge-success' : 'badge-neutral'}`}>
                        {s.is_active ? 'active' : 'inactive'}
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-sm" onClick={() => selectServer(s)}>
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
          <h2>{selected.name}</h2>
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
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button className="btn" onClick={handleToggleActive}>
              <FontAwesomeIcon icon={selected.is_active ? faBan : faCheck} />{' '}
              {selected.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <button className="btn btn-danger" onClick={handleDeleteServer}>
              <FontAwesomeIcon icon={faTrash} /> Delete server
            </button>
          </div>

          <h3>GPUs</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Index</th>
                  <th>Model</th>
                  <th>RAM</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {gpus.map((g) => (
                  <tr key={g.id}>
                    <td>GPU{g.index_on_server}</td>
                    <td>{g.model_name}</td>
                    <td>{(g.total_ram_mb / 1024).toFixed(0)} GB</td>
                    <td>
                      <span className={`badge ${g.is_active ? 'badge-success' : 'badge-neutral'}`}>
                        {g.is_active ? 'active' : 'inactive'}
                      </span>
                    </td>
                    <td style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-sm" onClick={() => handleRenameGpu(g)}>
                        Rename
                      </button>
                      <button className="btn btn-sm" onClick={() => handleToggleGpuActive(g)}>
                        {g.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => handleDeleteGpu(g)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 style={{ marginTop: 16 }}>Add GPU</h3>
          <div className="row">
            <div className="field" style={{ maxWidth: 100 }}>
              <label>Index</label>
              <input type="number" min={0} value={gpuIndex} onChange={(e) => setGpuIndex(Number(e.target.value))} />
            </div>
            <div className="field">
              <label>Model</label>
              <input value={gpuModel} onChange={(e) => setGpuModel(e.target.value)} placeholder="e.g. A100" />
            </div>
            <div className="field" style={{ maxWidth: 140 }}>
              <label>Total RAM (GB)</label>
              <input type="number" min={1} value={gpuRam} onChange={(e) => setGpuRam(Number(e.target.value))} />
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleAddGpu}>
            Add GPU
          </button>
        </div>
      )}
    </div>
  )
}
