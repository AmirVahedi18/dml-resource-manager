import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleCheck, faKey } from '@fortawesome/free-solid-svg-icons'
import { useState, type FormEvent } from 'react'
import { errorMessage } from '../api/errorMessage'
import { authApi } from '../api/endpoints'

export function ChangePasswordPage() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await authApi.changePassword(oldPassword, newPassword)
      setSuccess('Password changed.')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1>
        <FontAwesomeIcon icon={faKey} /> Change Password
      </h1>
      <form className="card password-form" onSubmit={handleSubmit}>
        {error && <div className="error-banner">{error}</div>}
        {success && (
          <div className="success-banner">
            <FontAwesomeIcon icon={faCircleCheck} /> {success}
          </div>
        )}
        <div className="field">
          <label>Current password</label>
          <input type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} required />
        </div>
        <div className="field">
          <label>New password</label>
          <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
        </div>
        <div className="field">
          <label>Confirm new password</label>
          <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Change password'}
        </button>
      </form>
    </div>
  )
}
