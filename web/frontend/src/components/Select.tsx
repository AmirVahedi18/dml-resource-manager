import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faChevronDown } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { fadeSlideVariants } from '../motion'

export interface SelectOption<T extends string | number> {
  value: T
  label: string
}

interface Props<T extends string | number> {
  value: T | null
  options: SelectOption<T>[]
  placeholder?: string
  disabled?: boolean
  onChange: (value: T) => void
}

/** Modern popover select, replacing the browser's native `<select>` dropdown. */
export function Select<T extends string | number>({ value, options, placeholder, disabled, onChange }: Props<T>) {
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
      <button type="button" className="date-picker-trigger" disabled={disabled} onClick={() => setOpen((o) => !o)}>
        <span className={selectedOption ? undefined : 'muted'}>{selectedOption?.label ?? placeholder ?? 'Select…'}</span>
        <span className="date-picker-icon" aria-hidden>
          <FontAwesomeIcon icon={faChevronDown} />
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div className="time-select-popover" variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
