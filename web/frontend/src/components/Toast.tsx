import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleCheck, faCircleExclamation, faCircleInfo, faXmark } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { toastVariants } from '../motion'

/*
 * Lightweight toast system.
 *
 * Replaces mid-page inline success banners (which appeared below the fold, so users
 * often never saw them) with transient, corner-anchored notifications. Wrap the app in
 * <ToastProvider> once, then call the `useToast()` API from anywhere:
 *
 *     const toast = useToast()
 *     toast.success('Reservation created.')
 *     toast.error('Something went wrong.')
 */

type ToastKind = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  kind: ToastKind
  message: ReactNode
}

interface ToastApi {
  success: (message: ReactNode) => void
  error: (message: ReactNode) => void
  info: (message: ReactNode) => void
}

const ToastContext = createContext<ToastApi | null>(null)

/** Access the toast API. Must be called inside <ToastProvider>. */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

const AUTO_DISMISS_MS = 10000

const ICONS: Record<ToastKind, typeof faCircleCheck> = {
  success: faCircleCheck,
  error: faCircleExclamation,
  info: faCircleInfo,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const remove = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (kind: ToastKind, message: ReactNode) => {
      const id = nextId.current++
      setToasts((list) => [...list, { id, kind, message }])
      window.setTimeout(() => remove(id), AUTO_DISMISS_MS)
    },
    [remove],
  )

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-viewport" aria-live="polite" aria-relevant="additions">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              className={`toast toast-${t.kind}`}
              role={t.kind === 'error' ? 'alert' : 'status'}
              variants={toastVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <FontAwesomeIcon icon={ICONS[t.kind]} className="toast-icon" aria-hidden />
              <span className="toast-msg">{t.message}</span>
              <button
                type="button"
                className="toast-close"
                aria-label="Dismiss notification"
                onClick={() => remove(t.id)}
              >
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
