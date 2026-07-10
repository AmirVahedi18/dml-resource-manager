import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { errorMessage } from '../api/errorMessage'
import { useAuth } from '../auth/AuthContext'
import { AppFooter } from '../components/AppFooter'
import { ThemeToggle } from '../components/ThemeToggle'
import { useToast } from '../components/Toast'

export function LoginPage() {
  const { user, login } = useAuth()
  const toast = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await login(username, password)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <div style={{ position: 'absolute', top: 16, right: 20 }}>
        <ThemeToggle />
      </div>
      <form className="card login-card" onSubmit={handleSubmit}>
        <img src="/logo.png" alt="" className="login-logo" />
        <h1 className="login-title">DML Resource Manager</h1>
        <p className="muted" style={{ marginBottom: 16, textAlign: 'center' }}>
          Sign in with the username and password your lab admin gave you.
        </p>
        <div className="field">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: '100%', justifyContent: 'center' }}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <AppFooter />
    </div>
  )
}
