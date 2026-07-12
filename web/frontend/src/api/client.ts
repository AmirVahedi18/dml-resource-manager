const TOKEN_KEY = 'dml_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Fired when a request comes back 401 so the app-level auth context can drop the session and
 * redirect to /login -- kept as a DOM event rather than a direct import so this module never has
 * to know about React/router state. */
export const AUTH_EXPIRED_EVENT = 'dml:auth-expired'

/** A plain-English fallback per status code, used whenever the response has no curated `detail`
 * string (or, for 5xx, even if it does -- an unexpected server error's `detail` may contain raw
 * exception text/a traceback, which must never reach the user). */
function friendlyStatusFallback(status: number): string {
  switch (status) {
    case 400:
      return 'That request could not be processed.'
    case 401:
      return 'You need to sign in again.'
    case 403:
      return "You don't have permission to do that."
    case 404:
      return 'That could not be found.'
    case 409:
      return 'That conflicts with something that already exists.'
    case 422:
      return 'Please check your input and try again.'
    default:
      return status >= 500
        ? 'Something went wrong on our end. Please try again in a moment.'
        : 'Something went wrong. Please try again.'
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; query?: Record<string, string | number | boolean | undefined> } = {}
): Promise<T> {
  const { method = 'GET', body, query } = options

  let url = path
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) params.set(key, String(value))
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }

  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    // The request never reached the server (offline, DNS failure, CORS, etc.) -- the browser's
    // own error text here is inconsistent and technical (e.g. "Failed to fetch"), so replace it.
    throw new ApiError(0, "Couldn't reach the server. Check your connection and try again.")
  }

  if (res.status === 401) {
    clearToken()
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
  }

  if (!res.ok) {
    // Only a curated, string `detail` from a deliberate 4xx HTTPException is trustworthy to show
    // verbatim. A 5xx `detail` may carry an unhandled exception's raw text, and FastAPI's default
    // validation-error `detail` is a list of objects, not a string -- neither should ever reach
    // the user, so both fall back to a plain-English default for their status code.
    let detail: string | undefined
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') detail = data.detail
    } catch {
      // response wasn't JSON
    }
    if (res.status >= 500 || !detail) detail = friendlyStatusFallback(res.status)
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
