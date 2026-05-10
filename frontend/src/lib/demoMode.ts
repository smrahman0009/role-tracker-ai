/**
 * Demo-mode flag + helpers.
 *
 * When the flag is set, the api.ts request layer routes every call
 * to canned fixtures (no backend, no Anthropic, no clipboard with
 * real data). Used by the public "Try Demo" entry on the login page
 * so unauthenticated visitors can explore the full UI without
 * needing a token.
 *
 * Storage: localStorage. Persists across page reloads but not
 * across browsers / devices. Cleared by signing in normally or by
 * calling exitDemoMode() (which the persistent demo banner offers
 * as a "Sign in for real account" action).
 *
 * Demo state itself (saved letters, applied toggles, etc.) is NOT
 * stored — it lives in React state and resets on reload. This is
 * intentional: each visit feels fresh, and we never accumulate
 * private data on the visitor's machine.
 */

const DEMO_FLAG_KEY = "rt:demo_mode";
/** Synthetic user_id used in URLs while in demo. Tracks the value
 *  the LoginPage seeds into auth storage. Kept here so the
 *  interceptor and the route helpers agree on the spelling. */
export const DEMO_USER_ID = "demo";

export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(DEMO_FLAG_KEY) === "1";
}

export function enterDemoMode(): void {
  window.localStorage.setItem(DEMO_FLAG_KEY, "1");
}

export function exitDemoMode(): void {
  window.localStorage.removeItem(DEMO_FLAG_KEY);
}
