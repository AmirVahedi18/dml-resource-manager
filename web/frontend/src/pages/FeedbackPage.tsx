import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faComment } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState, type FormEvent } from 'react'
import { errorMessage } from '../api/errorMessage'
import { feedbackApi } from '../api/endpoints'
import type { FeedbackCategory, FeedbackOut } from '../api/types'
import { Select } from '../components/Select'
import { useToast } from '../components/Toast'
import { fadeSlideVariants, fadeVariants } from '../motion'
import { formatDateTime } from '../utils/formatDate'

const CATEGORY_OPTIONS: { value: FeedbackCategory; label: string }[] = [
  { value: 'BUG', label: 'Bug' },
  { value: 'PROBLEM', label: 'Problem' },
  { value: 'SUGGESTION', label: 'Suggestion' },
  { value: 'OTHER', label: 'Other' },
]

const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  BUG: 'Bug',
  PROBLEM: 'Problem',
  SUGGESTION: 'Suggestion',
  OTHER: 'Other',
}

export function FeedbackPage() {
  const toast = useToast()
  const [category, setCategory] = useState<FeedbackCategory>('BUG')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<FeedbackOut[] | null>(null)

  function reload() {
    feedbackApi.list().then(setFeedback).catch((e) => toast.error(errorMessage(e)))
  }

  useEffect(reload, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!message.trim()) return
    setBusy(true)
    try {
      await feedbackApi.create(category, message.trim())
      toast.success('Feedback submitted. Thanks!')
      setMessage('')
      setCategory('BUG')
      reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faComment} /> Feedback
      </h1>

      <form className="card" onSubmit={handleSubmit}>
        <div className="field" style={{ maxWidth: 260 }}>
          <label>Category</label>
          <Select value={category} options={CATEGORY_OPTIONS} onChange={setCategory} />
        </div>
        <div className="field">
          <label>What's the issue or idea?</label>
          <textarea
            required
            maxLength={2000}
            rows={5}
            placeholder="Describe a bug, a problem you ran into, or a suggestion…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-primary" type="submit" disabled={busy || !message.trim()}>
            {busy ? 'Submitting…' : 'Submit feedback'}
          </button>
        </div>
      </form>

      <div className="card">
        <h2>Your submitted feedback</h2>
        <AnimatePresence mode="wait">
          {feedback?.length === 0 && (
            <motion.p key="empty" className="muted" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              You haven't submitted any feedback yet.
            </motion.p>
          )}
          {feedback && feedback.length > 0 && (
            <motion.div key="list" variants={fadeVariants} initial="initial" animate="animate" exit="exit">
              <AnimatePresence>
                {feedback.map((f) => (
                  <motion.div
                    key={f.id}
                    className="feedback-item"
                    layout
                    variants={fadeSlideVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                  >
                    <div className="feedback-item-row">
                      <span className="badge badge-neutral">{CATEGORY_LABEL[f.category]}</span>
                      <span className="muted">{formatDateTime(new Date(f.created_at + 'Z'))}</span>
                    </div>
                    <p style={{ marginTop: 8, marginBottom: 0 }}>{f.message}</p>
                  </motion.div>
                ))}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
