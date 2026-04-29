/**
 * Auth storage helpers — wraps localStorage so we don't sprinkle
 * `localStorage.getItem(...)` calls across the codebase. If we ever
 * swap to sessionStorage / cookies, only this file changes.
 *
 * Two values stored:
 *   - user_id   — the identity passed in URL paths (/users/{user_id}/...)
 *   - app_token — the bearer token sent in the Authorization header
 *                 (optional — empty token works in dev when the backend's
 *                 APP_TOKEN env var is unset)
 */

const KEY_USER_ID = "rt:user_id";
const KEY_APP_TOKEN = "rt:app_token";

export interface AuthState {
  userId: string | null;
  appToken: string | null;
}

export function getAuth(): AuthState {
  return {
    userId: localStorage.getItem(KEY_USER_ID),
    appToken: localStorage.getItem(KEY_APP_TOKEN),
  };
}

export function setAuth(userId: string, appToken: string): void {
  localStorage.setItem(KEY_USER_ID, userId);
  localStorage.setItem(KEY_APP_TOKEN, appToken);
}

export function clearAuth(): void {
  localStorage.removeItem(KEY_USER_ID);
  localStorage.removeItem(KEY_APP_TOKEN);
}

export function isAuthenticated(): boolean {
  // Authenticated = we know which user this is. Token is optional —
  // backend may have APP_TOKEN unset (dev mode).
  return Boolean(localStorage.getItem(KEY_USER_ID));
}
