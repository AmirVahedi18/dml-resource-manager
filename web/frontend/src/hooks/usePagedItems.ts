import { useEffect, useState } from 'react'

/** Client-side pagination for a list that's already fully loaded (bounded by headcount/hardware,
 * not by lab-wide activity) -- slices `items` into one page instead of round-tripping the server. */
export function usePagedItems<T>(items: T[], pageSize = 20) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))

  useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  const pageItems = items.slice((page - 1) * pageSize, page * pageSize)
  return { page, setPage, totalPages, pageItems }
}
