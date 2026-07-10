import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCheck, faServer } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import type { ServerAdminOut } from '../api/types'
import { fadeSlideVariants, fadeVariants } from '../motion'

interface Props {
  servers: ServerAdminOut[]
  selected: number[]
  onToggle: (serverId: number) => void
}

export function ServerAccessChips({ servers, selected, onToggle }: Props) {
  return (
    <AnimatePresence mode="wait">
      {servers.length === 0 ? (
        <motion.span key="empty" className="muted" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
          No servers configured yet.
        </motion.span>
      ) : (
        <motion.div key="chips" className="chip-group" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
          <AnimatePresence>
            {servers.map((s) => {
              const active = selected.includes(s.id)
              return (
                <motion.button
                  key={s.id}
                  type="button"
                  layout
                  className={`chip${active ? ' chip-active' : ''}`}
                  aria-pressed={active}
                  onClick={() => onToggle(s.id)}
                  variants={fadeSlideVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  <FontAwesomeIcon icon={active ? faCheck : faServer} fixedWidth />
                  {s.name}
                </motion.button>
              )
            })}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
