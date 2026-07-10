import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faClock } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useRef, useState } from 'react'

export interface TimeOption {
  value: string
  label: string
}

interface Props {
  value: string
  options: TimeOption[]
  disabled?: boolean
  onChange: (value: string) => void
}

/** Modern popover time list, replacing the browser's native `<select>` dropdown. */
export function TimeSelect({ value, options, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selectedRef = useRef<HTMLButtonElement>(null)

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

  useEffect(() => {
    if (open) selectedRef.current?.scrollIntoView({ block: 'nearest' })
  }, [open])

  const selectedOption = options.find((o) => o.value === value)

  return (
    <div className="time-select" ref={rootRef}>
      <button
        type="button"
        className="date-picker-trigger"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <span>{selectedOption?.label ?? 'No times available today'}</span>
        <span className="date-picker-icon" aria-hidden>
          <FontAwesomeIcon icon={faClock} />
        </span>
      </button>

      {open && (
        <div className="time-select-popover">
          {options.map((o) => (
            <button
              key={o.value}
              ref={o.value === value ? selectedRef : undefined}
              type="button"
              className={`time-select-option${o.value === value ? ' time-select-option-selected' : ''}`}
              onClick={() => {
                onChange(o.value)
                setOpen(false)
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
