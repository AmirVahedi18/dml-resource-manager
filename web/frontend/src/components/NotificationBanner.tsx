import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation, faXmark } from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { notificationsApi } from '../api/endpoints'
import type { NotificationOut } from '../api/types'
import { fadeSlideVariants } from '../motion'

/**
 * Persistent banners for events a student needs to know about even if they weren't online when
 * it happened -- e.g. a GPU/server they use being deactivated (their reservations there got
 * suspended) or reactivated (those reservations resumed). Fetched once when the app shell mounts
 * (login, or a full page reload/revisit), and each banner sticks around until dismissed.
 */
export function NotificationBanner() {
  const [notifications, setNotifications] = useState<NotificationOut[]>([])

  useEffect(() => {
    notificationsApi.list().then(setNotifications).catch(() => {})
  }, [])

  async function dismiss(id: number) {
    setNotifications((list) => list.filter((n) => n.id !== id))
    try {
      await notificationsApi.dismiss(id)
    } catch {
      // Best-effort -- if this fails the banner will just reappear on the next page load.
    }
  }

  if (notifications.length === 0) return null

  return (
    <div className="notification-banners">
      <AnimatePresence>
        {notifications.map((n) => (
          <motion.div
            key={n.id}
            className="notification-banner"
            layout
            variants={fadeSlideVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <FontAwesomeIcon icon={faTriangleExclamation} className="notification-banner-icon" aria-hidden />
            <span className="notification-banner-msg">{n.message}</span>
            <button
              type="button"
              className="notification-banner-close"
              aria-label="Dismiss"
              onClick={() => dismiss(n.id)}
            >
              <FontAwesomeIcon icon={faXmark} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
