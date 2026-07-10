import { motion } from 'framer-motion'
import { Fragment, useEffect, useState } from 'react'
import { scheduleApi } from '../api/endpoints'
import type { GpuOut, ServerOut } from '../api/types'
import { fadeVariants } from '../motion'

interface Props {
  serverId: number | null
  gpuId: number | null
  onGpuChange: (serverId: number | null, gpuId: number | null, gpu: GpuOut | null) => void
}

export function GpuPicker({ serverId, gpuId, onGpuChange }: Props) {
  const [servers, setServers] = useState<ServerOut[]>([])
  const [gpusByServer, setGpusByServer] = useState<Record<number, GpuOut[]>>({})

  useEffect(() => {
    scheduleApi.servers().then(setServers)
  }, [])

  useEffect(() => {
    if (servers.length === 0) return
    let cancelled = false
    Promise.all(servers.map((s) => scheduleApi.gpus(s.id).then((gpus) => [s.id, gpus] as const))).then((entries) => {
      if (cancelled) return
      setGpusByServer(Object.fromEntries(entries))
    })
    return () => {
      cancelled = true
    }
  }, [servers])

  if (servers.length === 0) {
    return <span className="muted">No accessible servers yet.</span>
  }

  // Lay servers + their GPUs out as one shared 2-column grid (not one grid per server) so
  // every GPU button sits in the same column track and is sized to the widest one, while
  // each server box spans exactly the rows its own GPUs occupy.
  let rowCursor = 1
  const rows = servers.map((s) => {
    const gpus = gpusByServer[s.id] ?? []
    const rowStart = rowCursor
    rowCursor += Math.max(gpus.length, 1)
    return { server: s, gpus, rowStart }
  })

  return (
    <div className="picker-server-list">
      {rows.map(({ server: s, gpus, rowStart }) => (
        <Fragment key={s.id}>
          <motion.div
            className={`picker-server-box${serverId === s.id ? ' picker-server-box-active' : ''}`}
            style={{ gridColumn: 1, gridRow: `${rowStart} / span ${Math.max(gpus.length, 1)}` }}
            variants={fadeVariants}
            initial="initial"
            animate="animate"
          >
            <span className="picker-btn-title">{s.name}</span>
          </motion.div>
          {gpus.length === 0 ? (
            <span className="muted" style={{ gridColumn: 2, gridRow: rowStart }}>
              No GPUs on this server.
            </span>
          ) : (
            gpus.map((g, i) => (
              <button
                key={g.id}
                type="button"
                className={`picker-btn${gpuId === g.id ? ' picker-btn-active' : ''}`}
                style={{ gridColumn: 2, gridRow: rowStart + i }}
                onClick={() => onGpuChange(s.id, g.id, g)}
              >
                <span className="picker-btn-title">
                  GPU{g.index_on_server} — {g.model_name}
                </span>
                <span className="picker-btn-sub">{(g.total_ram_mb / 1024).toFixed(0)} GB</span>
              </button>
            ))
          )}
        </Fragment>
      ))}
    </div>
  )
}
