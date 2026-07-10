import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { ThemeProvider } from './theme/ThemeContext'
import { ToastProvider } from './components/Toast'
import { NavShell } from './components/NavShell'
import { LoginPage } from './pages/LoginPage'
import { ReservePage } from './pages/ReservePage'
import { WatchesPage } from './pages/WatchesPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { AdminUsersPage } from './pages/admin/AdminUsersPage'
import { AdminServersPage } from './pages/admin/AdminServersPage'
import { AdminRegulationPage } from './pages/admin/AdminRegulationPage'
import { AdminReservationsPage } from './pages/admin/AdminReservationsPage'
import { AdminUsageReportPage } from './pages/admin/AdminUsageReportPage'

function App() {
  return (
    // ToastProvider sits above the router so any page/component can raise toasts.
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route element={<ProtectedRoute />}>
                <Route element={<NavShell />}>
                  <Route index element={<ReservePage />} />
                  <Route path="/watches" element={<WatchesPage />} />
                  <Route path="/change-password" element={<ChangePasswordPage />} />

                  <Route element={<ProtectedRoute adminOnly />}>
                    <Route path="/admin/users" element={<AdminUsersPage />} />
                    <Route path="/admin/servers" element={<AdminServersPage />} />
                    <Route path="/admin/regulation" element={<AdminRegulationPage />} />
                    <Route path="/admin/reservations" element={<AdminReservationsPage />} />
                    <Route path="/admin/usage" element={<AdminUsageReportPage />} />
                  </Route>
                </Route>
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  )
}

export default App
