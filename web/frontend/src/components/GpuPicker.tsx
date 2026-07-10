import { useEffect, useState } from 'react'
import { scheduleApi } from '../api/endpoints'
import type { GpuOut, ServerOut } from '../api/types'

interface Props {
  serverId: number | null
  gpuId: number | null
  onServerChange: (id: number | null) => void
  onGpuChange: (id: number | null, gpu: GpuOut | null) => void
}

export function GpuPicker({ serverId, gpuId, onServerChange, onGpuChange }: Props) {
  const [servers, setServers] = useState<ServerOut[]>([])
  const [gpus, setGpus] = useState<GpuOut[]>([])

  useEffect(() => {
    scheduleApi.servers().then(setServers)
  }, [])

  useEffect(() => {
    if (serverId == null) {
      setGpus([])
      return
    }
    scheduleApi.gpus(serverId).then(setGpus)
  }, [serverId])

  return (
    <div>
      <div className="field">
        <label>Server</label>
        {servers.length === 0 ? (
          <span className="muted">No accessible servers yet.</span>
        ) : (
          <div className="picker-grid">
            {servers.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`picker-btn${serverId === s.id ? ' picker-btn-active' : ''}`}
                onClick={() => {
                  onServerChange(s.id)
                  onGpuChange(null, null)
                }}
              >
                <span className="picker-btn-title">{s.name}</span>
                {s.description && <span className="picker-btn-sub">{s.description}</span>}
              </button>
            ))}
          </div>
        )}
      </div>

      {serverId != null && (
        <div className="field">
          <label>GPU</label>
          {gpus.length === 0 ? (
            <span className="muted">No GPUs on this server.</span>
          ) : (
            <div className="picker-grid">
              {gpus.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  className={`picker-btn${gpuId === g.id ? ' picker-btn-active' : ''}`}
                  onClick={() => onGpuChange(g.id, g)}
                >
                  <span className="picker-btn-title">
                    GPU{g.index_on_server} — {g.model_name}
                  </span>
                  <span className="picker-btn-sub">{(g.total_ram_mb / 1024).toFixed(0)} GB</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
