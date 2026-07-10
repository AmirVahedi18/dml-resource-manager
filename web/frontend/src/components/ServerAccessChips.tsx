import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCheck, faServer } from '@fortawesome/free-solid-svg-icons'
import type { ServerAdminOut } from '../api/types'

interface Props {
  servers: ServerAdminOut[]
  selected: number[]
  onToggle: (serverId: number) => void
}

export function ServerAccessChips({ servers, selected, onToggle }: Props) {
  if (servers.length === 0) {
    return <span className="muted">No servers configured yet.</span>
  }
  return (
    <div className="chip-group">
      {servers.map((s) => {
        const active = selected.includes(s.id)
        return (
          <button
            key={s.id}
            type="button"
            className={`chip${active ? ' chip-active' : ''}`}
            aria-pressed={active}
            onClick={() => onToggle(s.id)}
          >
            <FontAwesomeIcon icon={active ? faCheck : faServer} fixedWidth />
            {s.name}
          </button>
        )
      })}
    </div>
  )
}
