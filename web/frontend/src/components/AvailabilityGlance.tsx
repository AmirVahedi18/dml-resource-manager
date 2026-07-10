import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBolt, faRotate } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { scheduleApi } from '../api/endpoints'
import type { GpuOut, OccupancyChartData, ServerOverviewOut } from '../api/types'
import { OccupancyChart } from './OccupancyChart'
import { useToast } from './Toast'
import { fadeSlideVariants, fadeVariants } from '../motion'
import { formatDateTime } from '../utils/formatDate'

/*
 * At-a-glance live availability across every server the user can access.
 *
 * This is the "what's free right now" summary that used to be missing: previously a user
 * had to drill server -> GPU -> chart just to learn if anything was open. Each GPU tile is
 * clickable and preselects that GPU in the booking form below (onPick), turning the glance
 * into the primary entry point for a reservation.
 */

interface Props {
  selectedGpuId: number | null
  onPick: (serverId: number, gpu: GpuOut) => void
  /** Bump to refetch (e.g. after a booking/cancel changes occupancy). */
  reloadSignal?: number
  /** Range selection + chart for the selected GPU, shown alongside the glance tiles. */
  days: number
  availableRangeOptions: number[]
  onDaysChange: (days: number) => void
  chart: OccupancyChartData | null
  tz: string
}

function gb(mb: number): string {
  return (mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)
}

export function AvailabilityGlance({
  selectedGpuId,
  onPick,
  reloadSignal = 0,
  days,
  availableRangeOptions,
  onDaysChange,
  chart,
  tz,
}: Props) {
  const toast = useToast()
  const [servers, setServers] = useState<ServerOverviewOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    scheduleApi
      .overview()
      .then((data) => !cancelled && setServers(data))
      .catch(() => {
        if (cancelled) return
        setError('Could not load live availability.')
        toast.error('Could not load live availability.')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadSignal])

  return (
    <div className="card card-feature">
      <div className="glance-layout">
        <div className="glance-left">
          <h2>
            <FontAwesomeIcon icon={faBolt} /> Available now
          </h2>

          <AnimatePresence mode="wait">
            {servers === null && !error && (
              // Skeleton tiles while the overview loads.
              <motion.div
                key="skeleton"
                className="glance-grid"
                variants={fadeVariants}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                {[0, 1, 2].map((i) => (
                  <div key={i} className="glance-gpu skeleton-tile" aria-hidden />
                ))}
              </motion.div>
            )}

            {servers && servers.length === 0 && (
              <motion.p
                key="empty"
                className="muted"
                variants={fadeVariants}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                No accessible servers yet. Ask your lab admin for access.
              </motion.p>
            )}
          </AnimatePresence>

          {servers?.map((server) => (
            <div key={server.id} className="glance-server">
              <div className="glance-server-name">{server.name}</div>
              {server.gpus.length === 0 ? (
                <p className="muted glance-empty">No GPUs on this server.</p>
              ) : (
                <div className="glance-grid">
                  {server.gpus.map((g) => {
                    const usedPct = Math.min(100, Math.round((g.used_ram_mb / Math.max(g.total_ram_mb, 1)) * 100))
                    const isFull = g.free_ram_mb <= 0
                    const isFree = g.used_ram_mb <= 0
                    const status = isFull ? 'full' : isFree ? 'free' : 'partial'
                    const selected = selectedGpuId === g.id
                    return (
                      <button
                        key={g.id}
                        type="button"
                        className={`glance-gpu glance-gpu-${status}${selected ? ' glance-gpu-selected' : ''}`}
                        aria-pressed={selected}
                        onClick={() =>
                          onPick(server.id, {
                            id: g.id,
                            server_id: server.id,
                            index_on_server: g.index_on_server,
                            model_name: g.model_name,
                            total_ram_mb: g.total_ram_mb,
                          })
                        }
                      >
                        <div className="glance-gpu-head">
                          <span className="glance-gpu-title">GPU{g.index_on_server}</span>
                          <span className={`badge badge-${isFull ? 'danger' : isFree ? 'success' : 'warn'}`}>
                            {isFull ? 'Full' : isFree ? 'Free' : `${gb(g.free_ram_mb)} GB free`}
                          </span>
                        </div>
                        <div className="glance-gpu-model">{g.model_name}</div>
                        <div className="glance-meter" title={`${gb(g.used_ram_mb)} / ${gb(g.total_ram_mb)} GB used`}>
                          <div className={`glance-meter-fill glance-meter-${status}`} style={{ width: `${usedPct}%` }} />
                        </div>
                        <div className="glance-gpu-foot mono">
                          {gb(g.free_ram_mb)} / {gb(g.total_ram_mb)} GB free
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          ))}

          <AnimatePresence>
            {servers && servers.length > 0 && (
              <motion.p
                key="hint"
                className="muted glance-hint"
                variants={fadeVariants}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                <FontAwesomeIcon icon={faRotate} /> Pick a GPU to fill in the booking form below.
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        <div className="glance-right">
          <AnimatePresence mode="wait">
            {chart ? (
              <motion.div key="chart" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                <OccupancyChart data={chart} />

                <div className="glance-range-picker">
                  <div className="segmented">
                    {availableRangeOptions.map((d) => (
                      <button
                        key={d}
                        type="button"
                        className={`segmented-option${days === d ? ' segmented-option-active' : ''}`}
                        onClick={() => onDaysChange(d)}
                      >
                        {d === 1 ? 'Today' : `${d}d`}
                      </button>
                    ))}
                  </div>
                </div>

                <AnimatePresence>
                  {chart.segments.length > 0 && (
                    <motion.details
                      key="reservations"
                      className="glance-reservations"
                      variants={fadeSlideVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                    >
                      <summary>Reservations in range ({chart.segments.length})</summary>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>User</th>
                              <th>Start</th>
                              <th>End</th>
                              <th>RAM</th>
                            </tr>
                          </thead>
                          <tbody>
                            <AnimatePresence>
                              {chart.segments.map((s) => (
                                <motion.tr
                                  key={s.reservation_id}
                                  layout
                                  variants={fadeSlideVariants}
                                  initial="initial"
                                  animate="animate"
                                  exit="exit"
                                >
                                  <td>{s.user}</td>
                                  <td className="num">{formatDateTime(new Date(s.start), tz)}</td>
                                  <td className="num">{formatDateTime(new Date(s.end), tz)}</td>
                                  <td className="num">{(s.ram_mb / 1024).toFixed(1)} GB</td>
                                </motion.tr>
                              ))}
                            </AnimatePresence>
                          </tbody>
                        </table>
                      </div>
                    </motion.details>
                  )}
                </AnimatePresence>
              </motion.div>
            ) : (
              <motion.p
                key="placeholder"
                className="muted picker-placeholder"
                variants={fadeVariants}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                Pick a GPU to see its availability chart.
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
