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
  return (
    <div className="segmented" role="radiogroup" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          className={`segmented-option${o.value === value ? ' segmented-option-active' : ''}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
