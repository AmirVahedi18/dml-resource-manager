import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft,
  faBell,
  faCalendarPlus,
  faChartLine,
  faClipboardList,
  faKey,
  faRightFromBracket,
  faScaleBalanced,
  faServer,
  faShieldHalved,
  faUser,
  type IconDefinition,
} from '@fortawesome/free-solid-svg-icons'
import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { AppFooter } from './AppFooter'
import { ConfirmDialog } from './ConfirmDialog'
import { ThemeToggle } from './ThemeToggle'

function Link({ to, icon, children }: { to: string; icon: IconDefinition; children: React.ReactNode }) {
  return (
    <NavLink to={to} end className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}>
      <FontAwesomeIcon icon={icon} fixedWidth className="sidebar-link-icon" /> {children}
    </NavLink>
  )
}

const STUDENT_TABS = [
  { to: '/', icon: faCalendarPlus, label: 'Reserve' },
  { to: '/watches', icon: faBell, label: 'Watches' },
]

const ADMIN_TABS = [
  { to: '/admin/users', icon: faUser, label: 'Users' },
  { to: '/admin/servers', icon: faServer, label: 'Servers' },
  { to: '/admin/regulation', icon: faScaleBalanced, label: 'Rules' },
  { to: '/admin/reservations', icon: faClipboardList, label: 'Reservations' },
  { to: '/admin/usage', icon: faChartLine, label: 'Usage' },
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
        <Link to="/watches" icon={faBell}>Watches</Link>
        <Link to="/change-password" icon={faKey}>Change Password</Link>
        <button type="button" className="sidebar-link sidebar-logout" onClick={() => setLogoutConfirmOpen(true)}>
          <FontAwesomeIcon icon={faRightFromBracket} fixedWidth className="sidebar-link-icon" /> Log out
        </button>

        {user?.is_admin && (
          <>
            <div className="sidebar-section-label">Admin</div>
            <Link to="/admin/users" icon={faUser}>Manage Users</Link>
            <Link to="/admin/servers" icon={faServer}>Manage Servers</Link>
            <Link to="/admin/regulation" icon={faScaleBalanced}>Regulation</Link>
            <Link to="/admin/reservations" icon={faClipboardList}>All Reservations</Link>
            <Link to="/admin/usage" icon={faChartLine}>Usage Report</Link>
          </>
        )}
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
          <Outlet />
          <AppFooter />
        </div>

        <nav className="bottom-nav">
          {inAdminArea && (
            <div className="admin-subnav">
              {ADMIN_TABS.map((t) => (
                <BottomNavLink key={t.to} to={t.to} icon={t.icon} label={t.label} />
              ))}
            </div>
          )}

          <div className="bottom-nav-row">
            {STUDENT_TABS.map((t) => (
              <BottomNavLink key={t.to} to={t.to} icon={t.icon} label={t.label} />
            ))}
            <BottomNavLink to="/change-password" icon={faKey} label="Password" />
            {user?.is_admin && !inAdminArea && (
              <BottomNavLink to="/admin/users" icon={faShieldHalved} label="Admin panel" />
            )}
            {inAdminArea && <BottomNavLink to="/" icon={faArrowLeft} label="Back" />}
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
