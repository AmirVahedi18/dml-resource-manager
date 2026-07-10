import { useEffect, useState } from 'react'
import { scheduleApi } from './endpoints'

export interface GpuLookupEntry {
  serverName: string
  indexOnServer: number
  modelName: string
}

/** Builds a gpu_id -> {serverName, indexOnServer, modelName} map from every server/GPU the current
 * user can see, so reservation/watch lists (which only carry gpu_id) can render a readable label
 * without a dedicated join endpoint. */
export function useGpuLookup(): Record<number, GpuLookupEntry> {
  const [lookup, setLookup] = useState<Record<number, GpuLookupEntry>>({})

  useEffect(() => {
    let cancelled = false
    async function load() {
      const servers = await scheduleApi.servers()
      const entries: Record<number, GpuLookupEntry> = {}
      await Promise.all(
        servers.map(async (server) => {
          const gpus = await scheduleApi.gpus(server.id)
          for (const gpu of gpus) {
            entries[gpu.id] = { serverName: server.name, indexOnServer: gpu.index_on_server, modelName: gpu.model_name }
          }
        })
      )
      if (!cancelled) setLookup(entries)
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  return lookup
}
