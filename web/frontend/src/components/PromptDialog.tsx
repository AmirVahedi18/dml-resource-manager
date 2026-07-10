import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { fadeVariants, modalVariants } from '../motion'

interface Props {
  open: boolean
  title: string
  label?: string
  initialValue?: string
  confirmLabel?: string
  cancelLabel?: string
  busy?: boolean
  onConfirm: (value: string) => void
  onCancel: () => void
}

export function PromptDialog({
  open,
  title,
  label,
  initialValue = '',
  confirmLabel = 'Save',
  cancelLabel = 'Cancel',
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  const [value, setValue] = useState(initialValue)

  useEffect(() => {
    if (open) setValue(initialValue)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onCancel])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-backdrop"
          variants={fadeVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onCancel()
          }}
        >
          <motion.div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="prompt-dialog-title"
            variants={modalVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <h3 id="prompt-dialog-title">{title}</h3>
            <div className="field" style={{ marginTop: 12, marginBottom: 0 }}>
              {label && <label>{label}</label>}
              <input
                autoFocus
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && value.trim()) onConfirm(value.trim())
                }}
              />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn" onClick={onCancel} disabled={busy}>
                {cancelLabel}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => value.trim() && onConfirm(value.trim())}
                disabled={busy || !value.trim()}
              >
                {busy ? 'Working…' : confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
