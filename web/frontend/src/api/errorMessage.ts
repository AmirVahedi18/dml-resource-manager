import { ApiError } from './client'

/** `ApiError` messages are already curated, plain-English text (see client.ts) and safe to show
 * verbatim. Anything else -- a raw JS `Error` thrown by a bug, or a non-Error value -- has no such
 * guarantee, so it always gets a generic, non-technical fallback instead of its raw `.message`. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  return 'Something went wrong. Please try again.'
}
