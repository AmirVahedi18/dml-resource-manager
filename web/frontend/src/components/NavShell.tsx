import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft,
  faCalendarPlus,
  faChartLine,
  faClipboardList,
  faComment,
  faEye,
  faKey,
  faRightFromBracket,
  faScaleBalanced,
  faServer,
  faShieldHalved,
  faUser,
  type IconDefinition,
} from '@fortawesome/free-solid-svg-icons'
import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { NavLink, useLocation, useOutlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { fadeSlideVariants, pageVariants } from '../motion'
import { AppFooter } from './AppFooter'
import { ConfirmDialog } from './ConfirmDialog'
import { NotificationBanner } from './NotificationBanner'
import { ThemeToggle } from './ThemeToggle'

function Link({ to, icon, children }: { to: string; icon: IconDefinition; children: React.ReactNode }) {
  return (
    <NavLink to={to} end className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}>
      <FontAwesomeIcon icon={icon} fixedWidth className="sidebar-link-icon" /> {children}
    </NavLink>
  )
}

const STUDENT_TABS = [{ to: '/', icon: faCalendarPlus, label: 'Reserve' }]

const ADMIN_TABS = [
  { to: '/admin/users', icon: faUser, label: 'Users' },
  { to: '/admin/servers', icon: faServer, label: 'Servers' },
  { to: '/admin/regulation', icon: faScaleBalanced, label: 'Rules' },
  { to: '/admin/reservations', icon: faClipboardList, label: 'Reservations' },
  { to: '/admin/watches', icon: faEye, label: 'Watches' },
  { to: '/admin/usage', icon: faChartLine, label: 'Usage' },
  { to: '/admin/feedback', icon: faComment, label: 'Feedback' },
]

function BottomNavLink({ to, icon, label }: { to: string; icon: IconDefinition; label: string }) {
  return (
    <NavLink to={to} end className={({ isActive }) => `bottom-nav-item${isActive ? ' active' : ''}`}>
      <span className="bottom-nav-icon" aria-hidden>
        <FontAwesomeIcon icon={icon} />
      </span>
      <span>{label}</span>
    </NavLink>
  )
}

export function NavShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  // Capture the routed page as a concrete element (frozen), rather than <Outlet /> which reads
  // the *live* router context. That lets AnimatePresence keep the OLD page mounted through its
  // exit animation instead of instantly swapping in the new route's content mid-fade.
  const outlet = useOutlet()
  const inAdminArea = location.pathname.startsWith('/admin')
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          Welcome back, {user?.full_name} {user?.is_admin && <span className="badge badge-neutral">admin</span>}
        </div>

        <div className="sidebar-section-label">Student</div>
        <Link to="/" icon={faCalendarPlus}>Reserve GPU</Link>
        <Link to="/feedback" icon={faComment}>Feedback</Link>
        <Link to="/change-password" icon={faKey}>Change Password</Link>
        <button type="button" className="sidebar-link sidebar-logout" onClick={() => setLogoutConfirmOpen(true)}>
          <FontAwesomeIcon icon={faRightFromBracket} fixedWidth className="sidebar-link-icon" /> Log out
        </button>

        <AnimatePresence>
          {user?.is_admin && (
            <motion.div
              style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
              variants={fadeSlideVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <div className="sidebar-section-label">Admin</div>
              <Link to="/admin/users" icon={faUser}>Manage Users</Link>
              <Link to="/admin/servers" icon={faServer}>Manage Servers</Link>
              <Link to="/admin/regulation" icon={faScaleBalanced}>Regulation</Link>
              <Link to="/admin/reservations" icon={faClipboardList}>All Reservations</Link>
              <Link to="/admin/watches" icon={faEye}>All Watches</Link>
              <Link to="/admin/usage" icon={faChartLine}>Usage Report</Link>
              <Link to="/admin/feedback" icon={faComment}>Feedback</Link>
            </motion.div>
          )}
        </AnimatePresence>
      </aside>

      <div className="main-area">
        <div className="topbar">
          <div className="topbar-titles">
            <img src="/logo.png" alt="" className="topbar-logo" />
            <div className="topbar-titles-text">
              <span className="topbar-brand">DML Resource Manager</span>
              <span className="topbar-welcome">
                Welcome back, {user?.full_name}{' '}
                {user?.is_admin && <span className="badge badge-neutral">admin</span>}
              </span>
            </div>
          </div>
          <ThemeToggle />
        </div>
        <div className="content">
          <NotificationBanner />
          {/* Animate only the routed page, keyed by pathname. mode="wait" fully fades the old
              page out before the new one appears; the banner and footer stay put. The key is
              also passed to the inner element so the frozen `outlet` swaps in sync. */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              {outlet}
            </motion.div>
          </AnimatePresence>
          <AppFooter />
        </div>

        <nav className="bottom-nav">
          <AnimatePresence>
            {inAdminArea && (
              <motion.div
                className="admin-subnav"
                variants={fadeSlideVariants}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                {ADMIN_TABS.map((t) => (
                  <BottomNavLink key={t.to} to={t.to} icon={t.icon} label={t.label} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="bottom-nav-row">
            {STUDENT_TABS.map((t) => (
              <BottomNavLink key={t.to} to={t.to} icon={t.icon} label={t.label} />
            ))}
            <BottomNavLink to="/feedback" icon={faComment} label="Feedback" />
            <BottomNavLink to="/change-password" icon={faKey} label="Password" />
            <AnimatePresence>
              {user?.is_admin && !inAdminArea && (
                <motion.div
                  key="admin-panel"
                  style={{ flex: 1, display: 'flex' }}
                  variants={fadeSlideVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  <BottomNavLink to="/admin/users" icon={faShieldHalved} label="Admin panel" />
                </motion.div>
              )}
              {inAdminArea && (
                <motion.div
                  key="back"
                  style={{ flex: 1, display: 'flex' }}
                  variants={fadeSlideVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  <BottomNavLink to="/" icon={faArrowLeft} label="Back" />
                </motion.div>
              )}
            </AnimatePresence>
            <button type="button" className="bottom-nav-item" onClick={() => setLogoutConfirmOpen(true)}>
              <span className="bottom-nav-icon" aria-hidden>
                <FontAwesomeIcon icon={faRightFromBracket} />
              </span>
              <span>Log out</span>
            </button>
          </div>
        </nav>
      </div>

      <ConfirmDialog
        open={logoutConfirmOpen}
        title="Log out?"
        message="You'll need to sign in again to continue."
        confirmLabel="Log out"
        cancelLabel="Stay signed in"
        danger={false}
        onConfirm={logout}
        onCancel={() => setLogoutConfirmOpen(false)}
      />
    </div>
  )
}
