import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleHalfStroke, faMoon, faSun, type IconDefinition } from '@fortawesome/free-solid-svg-icons'
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
      <FontAwesomeIcon icon={ICON[mode]} fixedWidth aria-hidden="true" />{' '}
      <span className="theme-toggle-label">{LABEL[mode]}</span>
    </button>
  )
}
