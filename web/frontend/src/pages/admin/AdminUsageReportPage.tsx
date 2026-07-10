import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCalendarDays, faChartLine, faMicrochip, faUser } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminUsageApi, scheduleApi } from '../../api/endpoints'
import type { OccupancyChartData, RankedUsageOut, RegulationOut } from '../../api/types'
import { DatePicker } from '../../components/DatePicker'
import { GpuPicker } from '../../components/GpuPicker'
import { OccupancyChart } from '../../components/OccupancyChart'
import { Segmented } from '../../components/Segmented'
import { useToast } from '../../components/Toast'
import { UsageBarChart } from '../../components/UsageBarChart'
import { fadeSlideVariants, fadeVariants } from '../../motion'
import { formatDateTime } from '../../utils/formatDate'

type RangeKey = 'today' | 'week' | 'month' | 'horizon'
const RANGE_LABELS: Record<RangeKey, string> = {
  today: 'Today',
  week: 'Past week',
  month: 'Past 30 days',
  horizon: 'Full booking horizon',
}

type UserMetric = 'gpu_hours' | 'ram_gb_hours'
const USER_METRIC_LABELS: Record<UserMetric, string> = {
  gpu_hours: 'GPU-hours',
  ram_gb_hours: 'GB-hours',
}

export function AdminUsageReportPage() {
  const toast = useToast()
  const [regulation, setRegulation] = useState<RegulationOut | null>(null)

  const [userRangeKey, setUserRangeKey] = useState<RangeKey>('week')
  const [userMetric, setUserMetric] = useState<UserMetric>('gpu_hours')
  const [userRanked, setUserRanked] = useState<RankedUsageOut | null>(null)

  const [gpuRangeKey, setGpuRangeKey] = useState<RangeKey>('week')
  const [gpuRanked, setGpuRanked] = useState<RankedUsageOut | null>(null)

  const [histServerId, setHistServerId] = useState<number | null>(null)
  const [histGpuId, setHistGpuId] = useState<number | null>(null)
  const [histStartDate, setHistStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [histDays, setHistDays] = useState(7)
  const [histChart, setHistChart] = useState<OccupancyChartData | null>(null)

  useEffect(() => {
    scheduleApi.regulation().then(setRegulation).catch((e) => toast.error(errorMessage(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function rangeFor(key: RangeKey): { start: Date; end: Date } {
    const now = new Date()
    if (key === 'today') {
      const start = new Date(now)
      start.setHours(0, 0, 0, 0)
      return { start, end: now }
    }
    const days = key === 'week' ? 7 : key === 'month' ? 30 : regulation?.booking_horizon_days ?? 90
    return { start: new Date(now.getTime() - days * 86400_000), end: now }
  }

  function loadRanked(
    metric: 'gpu_hours' | 'ram_gb_hours',
    groupBy: 'user' | 'gpu',
    key: RangeKey,
    setter: (data: RankedUsageOut) => void,
  ) {
    const { start, end } = rangeFor(key)
    adminUsageApi
      .ranked(start.toISOString(), end.toISOString(), metric, groupBy)
      .then(setter)
      .catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(() => {
    loadRanked(userMetric, 'user', userRangeKey, setUserRanked)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userRangeKey, userMetric, regulation])

  useEffect(() => {
    loadRanked('ram_gb_hours', 'gpu', gpuRangeKey, setGpuRanked)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gpuRangeKey, regulation])

  async function loadHistorical() {
    if (!histGpuId) return
    try {
      const data = await adminUsageApi.historicalAvailability(histGpuId, histStartDate, histDays)
      setHistChart(data)
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faChartLine} /> Usage Report
      </h1>

      <motion.div className="card" variants={fadeVariants} initial="initial" animate="animate">
        <h2>
          <FontAwesomeIcon icon={faUser} /> By User
        </h2>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <div className="field">
            <Segmented
              value={userRangeKey}
              options={(Object.keys(RANGE_LABELS) as RangeKey[]).map((k) => ({ value: k, label: RANGE_LABELS[k] }))}
              onChange={setUserRangeKey}
              ariaLabel="Range"
            />
          </div>
          <div className="field">
            <Segmented
              value={userMetric}
              options={(Object.keys(USER_METRIC_LABELS) as UserMetric[]).map((k) => ({
                value: k,
                label: USER_METRIC_LABELS[k],
              }))}
              onChange={setUserMetric}
              ariaLabel="Metric"
            />
          </div>
        </div>
        <AnimatePresence>
          {userRanked && (
            <motion.div variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              <UsageBarChart data={userRanked} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <motion.div className="card" variants={fadeVariants} initial="initial" animate="animate">
        <h2>
          <FontAwesomeIcon icon={faMicrochip} /> By GPU
        </h2>
        <div className="field">
          <Segmented
            value={gpuRangeKey}
            options={(Object.keys(RANGE_LABELS) as RangeKey[]).map((k) => ({ value: k, label: RANGE_LABELS[k] }))}
            onChange={setGpuRangeKey}
            ariaLabel="Range"
          />
        </div>
        <AnimatePresence>
          {gpuRanked && (
            <motion.div variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              <UsageBarChart data={gpuRanked} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <motion.div className="card" variants={fadeVariants} initial="initial" animate="animate">
        <h2>
          <FontAwesomeIcon icon={faCalendarDays} /> Historical Availability
        </h2>
        <div className="picker-layout" style={{ alignItems: 'start' }}>
          <div className="picker-layout-left">
            <GpuPicker
              serverId={histServerId}
              gpuId={histGpuId}
              onGpuChange={(sId, gId) => {
                setHistServerId(sId)
                setHistGpuId(gId)
              }}
            />

            <div style={{ marginTop: 16 }}>
              <div className="field">
                <label>Start date</label>
                <DatePicker value={histStartDate} onChange={setHistStartDate} />
              </div>
              <div className="field">
                <label>Days forward</label>
                <input type="number" min={1} value={histDays} onChange={(e) => setHistDays(Number(e.target.value))} />
              </div>
              <button className="btn btn-primary" onClick={loadHistorical} disabled={!histGpuId}>
                Show
              </button>
            </div>
          </div>

          <div className="picker-layout-right">
            <AnimatePresence>
              {histChart && (
                <motion.div variants={fadeVariants} initial="initial" animate="animate" exit="exit">
                  <OccupancyChart data={histChart} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <AnimatePresence>
          {histChart && histChart.segments.length > 0 && (
            <motion.div style={{ marginTop: 16 }} variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
              <h3>Reservations in range ({histChart.segments.length})</h3>
              <p className="muted" style={{ fontSize: 12, marginTop: -4, marginBottom: 8 }}>
                Includes cancelled reservations for an accurate historical record.
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Start</th>
                      <th>End</th>
                      <th>RAM</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <AnimatePresence>
                      {histChart.segments.map((s) => (
                        <motion.tr
                          key={s.reservation_id}
                          layout
                          variants={fadeSlideVariants}
                          initial="initial"
                          animate="animate"
                          exit="exit"
                        >
                          <td>{s.user}</td>
                          <td className="num">{formatDateTime(new Date(s.start), histChart.tz)}</td>
                          <td className="num">{formatDateTime(new Date(s.end), histChart.tz)}</td>
                          <td className="num">{(s.ram_mb / 1024).toFixed(1)} GB</td>
                          <td>
                            <span className={`badge ${s.cancelled ? 'badge-neutral' : 'badge-success'}`}>
                              {s.cancelled ? 'cancelled' : 'active'}
                            </span>
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
