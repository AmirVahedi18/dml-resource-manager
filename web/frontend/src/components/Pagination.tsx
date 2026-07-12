import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faChevronLeft, faChevronRight } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'

interface Props {
  page: number
  totalPages: number
  onChange: (page: number) => void
  /** Optional "Showing X-Y of Z" label; omit for purely client-side lists where it's obvious. */
  rangeLabel?: string
}

export function Pagination({ page, totalPages, onChange, rangeLabel }: Props) {
  if (totalPages <= 1) return null

  return (
    <div className="pagination">
      {rangeLabel && <span className="muted pagination-range">{rangeLabel}</span>}
      <div className="pagination-controls">
        <button className="btn btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          <FontAwesomeIcon icon={faChevronLeft} />
        </button>
        <span className="pagination-page num">
          Page{' '}
          {/* The current page number ticks with a small fade/rise so paging feels responsive. */}
          <span className="pagination-page-number">
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={page}
                style={{ display: 'inline-block' }}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.14, ease: 'easeOut' }}
              >
                {page}
              </motion.span>
            </AnimatePresence>
          </span>{' '}
          of {totalPages}
        </span>
        <button className="btn btn-sm" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
          <FontAwesomeIcon icon={faChevronRight} />
        </button>
      </div>
    </div>
  )
}
