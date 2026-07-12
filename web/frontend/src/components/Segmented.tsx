import { motion } from 'framer-motion'
import { useId } from 'react'

export interface SegmentedOption<T extends string | number> {
  value: T
  label: string
}

interface Props<T extends string | number> {
  value: T
  options: SegmentedOption<T>[]
  onChange: (value: T) => void
  ariaLabel?: string
}

/** Pill-shaped toggle group for a small, fixed set of mutually-exclusive options -- every choice
 * is visible and one click away, unlike a dropdown which hides them behind an open step. */
export function Segmented<T extends string | number>({ value, options, onChange, ariaLabel }: Props<T>) {
  // Unique per instance so the sliding pill never animates between separate segmented groups.
  const pillId = useId()
  return (
    <div className="segmented" role="radiogroup" aria-label={ariaLabel}>
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            className={`segmented-option${active ? ' segmented-option-active' : ''}`}
            onClick={() => onChange(o.value)}
          >
            {/* Shared-layout pill that slides from the previously-active option to this one.
                Rendered only under the active option; framer-motion animates its position. */}
            {active && (
              <motion.span
                layoutId={`segmented-pill-${pillId}`}
                className="segmented-indicator"
                transition={{ type: 'spring', stiffness: 380, damping: 32 }}
              />
            )}
            <span className="segmented-option-label">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}
