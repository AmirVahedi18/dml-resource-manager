import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleHalfStroke, faMoon, faSun, type IconDefinition } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useTheme } from '../theme/ThemeContext'

const ICON: Record<string, IconDefinition> = { system: faCircleHalfStroke, light: faSun, dark: faMoon }
const LABEL: Record<string, string> = { system: 'Follow device', light: 'Light mode', dark: 'Dark mode' }

export function ThemeToggle() {
  const { mode, cycleMode } = useTheme()

  return (
    <button
      type="button"
      className="btn btn-sm"
      onClick={cycleMode}
      title={`Theme: ${LABEL[mode]} (click to change)`}
      aria-label={`Theme: ${LABEL[mode]}. Click to change.`}
    >
      {/* Swap the icon with a quick rotate + fade whenever the mode cycles, so the toggle
          feels responsive. mode="wait" keeps a single icon on screen at a time. */}
      <span className="theme-toggle-icon" aria-hidden="true">
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={mode}
            style={{ display: 'inline-flex' }}
            initial={{ opacity: 0, rotate: -90, scale: 0.6 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={{ opacity: 0, rotate: 90, scale: 0.6 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            <FontAwesomeIcon icon={ICON[mode]} fixedWidth />
          </motion.span>
        </AnimatePresence>
      </span>{' '}
      <span className="theme-toggle-label">{LABEL[mode]}</span>
    </button>
  )
}
