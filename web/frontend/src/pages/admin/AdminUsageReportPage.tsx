import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCalendarDays, faChartLine, faMicrochip, faUser } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react'
import { errorMessage } from '../../api/errorMessage'
import { adminUsageApi, scheduleApi } from '../../api/endpoints'
import type { OccupancyChartData, RankedUsageOut, RegulationOut } from '../../api/types'
import { DatePicker } from '../../components/DatePicker'
import { GpuPicker } from '../../components/GpuPicker'
import { OccupancyChart } from '../../components/OccupancyChart'
import { Select } from '../../components/Select'
import { UsageBarChart } from '../../components/UsageBarChart'

type RangeKey = 'today' | 'week' | 'month' | 'horizon'
const RANGE_LABELS: Record<RangeKey, string> = {
  today: 'Today',
  week: 'Past week',
  month: 'Past 30 days',
  horizon: 'Full booking horizon',
}

export function AdminUsageReportPage() {
  const [tab, setTab] = useState<'user' | 'gpu' | 'historical'>('user')
  const [regulation, setRegulation] = useState<RegulationOut | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [rangeKey, setRangeKey] = useState<RangeKey>('week')
  const [ranked, setRanked] = useState<RankedUsageOut | null>(null)

  const [histServerId, setHistServerId] = useState<number | null>(null)
  const [histGpuId, setHistGpuId] = useState<number | null>(null)
  const [histStartDate, setHistStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [histDays, setHistDays] = useState(7)
  const [histChart, setHistChart] = useState<OccupancyChartData | null>(null)

  useEffect(() => {
    scheduleApi.regulation().then(setRegulation).catch((e) => setError(errorMessage(e)))
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

  function loadRanked(metric: 'gpu_hours' | 'ram_gb_hours', key: RangeKey) {
    const { start, end } = rangeFor(key)
    adminUsageApi
      .ranked(start.toISOString(), end.toISOString(), metric)
      .then(setRanked)
      .catch((e) => setError(errorMessage(e)))
  }

  useEffect(() => {
    if (tab === 'user') loadRanked('gpu_hours', rangeKey)
    if (tab === 'gpu') loadRanked('ram_gb_hours', rangeKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, rangeKey, regulation])

  async function loadHistorical() {
    if (!histGpuId) return
    setError(null)
    try {
      const data = await adminUsageApi.historicalAvailability(histGpuId, histStartDate, histDays)
      setHistChart(data)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faChartLine} /> Usage Report
      </h1>
      {error && <div className="error-banner">{error}</div>}

      <div className="tabs">
        <div className={`tab${tab === 'user' ? ' active' : ''}`} onClick={() => setTab('user')}>
          <FontAwesomeIcon icon={faUser} /> By User
        </div>
        <div className={`tab${tab === 'gpu' ? ' active' : ''}`} onClick={() => setTab('gpu')}>
          <FontAwesomeIcon icon={faMicrochip} /> By GPU
        </div>
        <div className={`tab${tab === 'historical' ? ' active' : ''}`} onClick={() => setTab('historical')}>
          <FontAwesomeIcon icon={faCalendarDays} /> Historical Availability
        </div>
      </div>

      {(tab === 'user' || tab === 'gpu') && (
        <div className="card">
          <div className="field" style={{ maxWidth: 220 }}>
            <label>Range</label>
            <Select
              value={rangeKey}
              options={(Object.keys(RANGE_LABELS) as RangeKey[]).map((k) => ({ value: k, label: RANGE_LABELS[k] }))}
              onChange={setRangeKey}
            />
          </div>
          {ranked && <UsageBarChart data={ranked} />}
        </div>
      )}

      {tab === 'historical' && (
        <div className="card">
          <GpuPicker
            serverId={histServerId}
            gpuId={histGpuId}
            onServerChange={setHistServerId}
            onGpuChange={(id) => setHistGpuId(id)}
          />
          <div className="row">
            <div className="field">
              <label>Start date</label>
              <DatePicker value={histStartDate} onChange={setHistStartDate} />
            </div>
            <div className="field">
              <label>Days forward</label>
              <input type="number" min={1} value={histDays} onChange={(e) => setHistDays(Number(e.target.value))} />
            </div>
          </div>
          <button className="btn btn-primary" onClick={loadHistorical} disabled={!histGpuId}>
            Show
          </button>
          {histChart && (
            <div style={{ marginTop: 16 }}>
              <OccupancyChart data={histChart} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
