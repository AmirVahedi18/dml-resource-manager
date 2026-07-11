import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleInfo } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { fadeSlideVariants } from '../motion'

interface Props {
  text: string
  label?: string
}

/** Small info icon that reveals an explanatory popover on click. */
export function InfoTooltip({ text, label = 'More information' }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

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

  return (
    <div className="info-tooltip" ref={rootRef}>
      <button
        type="button"
        className="info-tooltip-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-label={label}
        aria-expanded={open}
      >
        <FontAwesomeIcon icon={faCircleInfo} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="info-tooltip-popover" variants={fadeSlideVariants} initial="initial" animate="animate" exit="exit">
            {text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
