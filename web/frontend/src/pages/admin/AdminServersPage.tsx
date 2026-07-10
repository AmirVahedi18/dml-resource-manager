import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBan, faCheck, faServer, faTrash } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminServersApi } from '../../api/endpoints'
import type { GpuAdminOut, ServerAdminOut } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { PromptDialog } from '../../components/PromptDialog'
import { useToast } from '../../components/Toast'
import { fadeSlideVariants } from '../../motion'

export function AdminServersPage() {
  const toast = useToast()
  const [servers, setServers] = useState<ServerAdminOut[] | null>(null)

  const [newServerName, setNewServerName] = useState('')

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [gpus, setGpus] = useState<GpuAdminOut[]>([])

  const [gpuIndex, setGpuIndex] = useState(0)
  const [gpuModel, setGpuModel] = useState('')
  const [gpuRam, setGpuRam] = useState(24)

  const [pendingDeleteServer, setPendingDeleteServer] = useState(false)
  const [pendingDeleteGpu, setPendingDeleteGpu] = useState<GpuAdminOut | null>(null)
  const [pendingRenameGpu, setPendingRenameGpu] = useState<GpuAdminOut | null>(null)
  const [dialogBusy, setDialogBusy] = useState(false)

  function reloadServers() {
    adminServersApi.list().then(setServers).catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(reloadServers, [])

  const selected = servers?.find((s) => s.id === selectedId) ?? null

  function selectServer(s: ServerAdminOut) {
    setSelectedId(s.id)
    setRenameValue(s.name)
    adminServersApi.gpus(s.id).then(setGpus).catch((e) => toast.error(errorMessage(e)))
  }

  async function handleCreateServer() {
    if (!newServerName.trim()) return
    try {
      await adminServersApi.create(newServerName.trim())
      setNewServerName('')
      reloadServers()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleRename() {
    if (!selected) return
    try {
      await adminServersApi.rename(selected.id, renameValue)
      reloadServers()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleToggleActive() {
    if (!selected) return
    try {
      await adminServersApi.setActive(selected.id, !selected.is_active)
      reloadServers()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleDeleteServer() {
    if (!selected) return
    setDialogBusy(true)
    try {
      await adminServersApi.delete(selected.id)
      setPendingDeleteServer(false)
      setSelectedId(null)
      reloadServers()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDialogBusy(false)
    }
  }

  async function handleAddGpu() {
    if (!selected || !gpuModel.trim()) return
    try {
      await adminServersApi.addGpu(selected.id, gpuIndex, gpuModel.trim(), Math.round(gpuRam * 1024))
      setGpuModel('')
      adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleToggleGpuActive(g: GpuAdminOut) {
    try {
      await adminServersApi.setGpuActive(g.id, !g.is_active)
      if (selected) adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  async function handleRenameGpu(modelName: string) {
    if (!pendingRenameGpu) return
    setDialogBusy(true)
    try {
      await adminServersApi.renameGpu(pendingRenameGpu.id, modelName)
      setPendingRenameGpu(null)
      if (selected) adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDialogBusy(false)
    }
  }

  async function handleDeleteGpu() {
    if (!pendingDeleteGpu) return
    setDialogBusy(true)
    try {
      await adminServersApi.deleteGpu(pendingDeleteGpu.id)
      setPendingDeleteGpu(null)
      if (selected) adminServersApi.gpus(selected.id).then(setGpus)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDialogBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faServer} /> Manage Servers
      </h1>

      <div className="card">
        <h2>Add server</h2>
        <div className="row" style={{ alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div className="field" style={{ maxWidth: 240 }}>
            <label>Name</label>
            <input value={newServerName} onChange={(e) => setNewServerName(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={handleCreateServer} style={{ marginBottom: 12 }}>
            Add server
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Servers</h2>
        {servers && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <AnimatePresence>
                  {servers.map((s) => (
                    <motion.tr key={s.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                      <td>{s.name}</td>
                      <td>
                        <span className={`badge ${s.is_active ? 'badge-success' : 'badge-neutral'}`}>
                          {s.is_active ? 'active' : 'inactive'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-sm" onClick={() => selectServer(s)}>
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
          <h2>{selected.name}</h2>
          <div className="row" style={{ alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 16 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Rename</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} />
                <button className="btn btn-sm" onClick={handleRename}>
                  Save
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn" onClick={handleToggleActive}>
                <FontAwesomeIcon icon={selected.is_active ? faBan : faCheck} />{' '}
                {selected.is_active ? 'Deactivate' : 'Activate'}
              </button>
              <button className="btn btn-danger" onClick={() => setPendingDeleteServer(true)}>
                <FontAwesomeIcon icon={faTrash} /> Delete server
              </button>
            </div>
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
                <AnimatePresence>
                  {gpus.map((g) => (
                    <motion.tr key={g.id} layout variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
                      <td>GPU{g.index_on_server}</td>
                      <td>{g.model_name}</td>
                      <td>{(g.total_ram_mb / 1024).toFixed(0)} GB</td>
                      <td>
                        <span className={`badge ${g.is_active ? 'badge-success' : 'badge-neutral'}`}>
                          {g.is_active ? 'active' : 'inactive'}
                        </span>
                      </td>
                      <td style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                        <button className="btn btn-sm" onClick={() => setPendingRenameGpu(g)}>
                          Rename
                        </button>
                        <button className="btn btn-sm" onClick={() => handleToggleGpuActive(g)}>
                          {g.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button className="btn btn-sm btn-danger" onClick={() => setPendingDeleteGpu(g)}>
                          Delete
                        </button>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>

          <h3 style={{ marginTop: 16 }}>Add GPU</h3>
          <div className="row" style={{ alignItems: 'flex-end' }}>
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
            <button className="btn btn-primary" onClick={handleAddGpu} style={{ marginBottom: 12 }}>
              Add GPU
            </button>
          </div>
        </motion.div>
      )}
      </AnimatePresence>

      <ConfirmDialog
        open={pendingDeleteServer}
        title="Delete server?"
        message={
          selected && (
            <>
              Permanently delete <strong>{selected.name}</strong> and all its GPUs/reservations/watches? This cannot be
              undone.
            </>
          )
        }
        confirmLabel="Delete server"
        busy={dialogBusy}
        onConfirm={handleDeleteServer}
        onCancel={() => setPendingDeleteServer(false)}
      />

      <ConfirmDialog
        open={pendingDeleteGpu !== null}
        title="Delete GPU?"
        message={
          pendingDeleteGpu && (
            <>
              Permanently delete <strong>GPU{pendingDeleteGpu.index_on_server}</strong> and all its
              reservations/watches?
            </>
          )
        }
        confirmLabel="Delete GPU"
        busy={dialogBusy}
        onConfirm={handleDeleteGpu}
        onCancel={() => setPendingDeleteGpu(null)}
      />

      <PromptDialog
        open={pendingRenameGpu !== null}
        title="Rename GPU"
        label="Model name"
        initialValue={pendingRenameGpu?.model_name ?? ''}
        busy={dialogBusy}
        onConfirm={handleRenameGpu}
        onCancel={() => setPendingRenameGpu(null)}
      />
    </div>
  )
}
