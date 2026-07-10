import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCalendarDays } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { fadeSlideVariants } from '../motion'

const WEEKDAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
const pad = (n: number) => String(n).padStart(2, '0')

function parseDateStr(dateStr: string): { year: number; month: number; day: number } {
  const [year, month, day] = dateStr.split('-').map(Number)
  return { year, month, day }
}

function toDateStr(year: number, month: number, day: number): string {
  return `${year}-${pad(month)}-${pad(day)}`
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate()
}

function todayDateStr(): string {
  const now = new Date()
  return toDateStr(now.getFullYear(), now.getMonth() + 1, now.getDate())
}

function formatDisplay(dateStr: string): string {
  const { year, month, day } = parseDateStr(dateStr)
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

interface Props {
  value: string
  min?: string
  max?: string
  onChange: (dateStr: string) => void
}

/** Modern popover calendar, replacing the browser's native `<input type="date">` widget. */
export function DatePicker({ value, min, max, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const selected = parseDateStr(value)
  const [viewYear, setViewYear] = useState(selected.year)
  const [viewMonth, setViewMonth] = useState(selected.month)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const sel = parseDateStr(value)
    setViewYear(sel.year)
    setViewMonth(sel.month)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function goMonth(delta: number) {
    let m = viewMonth + delta
    let y = viewYear
    if (m < 1) {
      m = 12
      y -= 1
    } else if (m > 12) {
      m = 1
      y += 1
    }
    setViewMonth(m)
    setViewYear(y)
  }

  const firstWeekday = new Date(viewYear, viewMonth - 1, 1).getDay()
  const totalDays = daysInMonth(viewYear, viewMonth)
  const cells: (number | null)[] = [...Array(firstWeekday).fill(null), ...Array.from({ length: totalDays }, (_, i) => i + 1)]

  const minMonthStr = min ? `${parseDateStr(min).year}-${pad(parseDateStr(min).month)}` : null
  const maxMonthStr = max ? `${parseDateStr(max).year}-${pad(parseDateStr(max).month)}` : null
  const viewMonthStr = `${viewYear}-${pad(viewMonth)}`
  const canGoPrev = !minMonthStr || viewMonthStr > minMonthStr
  const canGoNext = !maxMonthStr || viewMonthStr < maxMonthStr

  return (
    <div className="date-picker" ref={rootRef}>
      <button type="button" className="date-picker-trigger" onClick={() => setOpen((o) => !o)}>
        <span>{formatDisplay(value)}</span>
        <span className="date-picker-icon" aria-hidden>
          <FontAwesomeIcon icon={faCalendarDays} />
        </span>
      </button>

      <AnimatePresence>
        {open && (
        <motion.div className="date-picker-popover" variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
          <div className="date-picker-header">
            <button type="button" className="date-picker-nav" disabled={!canGoPrev} onClick={() => goMonth(-1)} aria-label="Previous month">
              ‹
            </button>
            <span className="date-picker-title">
              {new Date(viewYear, viewMonth - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </span>
            <button type="button" className="date-picker-nav" disabled={!canGoNext} onClick={() => goMonth(1)} aria-label="Next month">
              ›
            </button>
          </div>

          <div className="date-picker-weekdays">
            {WEEKDAY_LABELS.map((w, i) => (
              <span key={i}>{w}</span>
            ))}
          </div>

          <div className="date-picker-grid">
            {cells.map((day, i) => {
              if (day === null) return <span key={i} />
              const dateStr = toDateStr(viewYear, viewMonth, day)
              const isSelected = dateStr === value
              const isToday = dateStr === todayDateStr()
              const isDisabled = (min && dateStr < min) || (max && dateStr > max)
              return (
                <button
                  key={i}
                  type="button"
                  disabled={!!isDisabled}
                  className={`date-picker-day${isSelected ? ' date-picker-day-selected' : ''}${
                    isToday && !isSelected ? ' date-picker-day-today' : ''
                  }`}
                  onClick={() => {
                    onChange(dateStr)
                    setOpen(false)
                  }}
                >
                  {day}
                </button>
              )
            })}
          </div>

          <div className="date-picker-footer">
            <button
              type="button"
              className="date-picker-today-btn"
              onClick={() => {
                const todayStr = todayDateStr()
                onChange(min && todayStr < min ? min : todayStr)
                setOpen(false)
              }}
            >
              Today
            </button>
          </div>
        </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
