"use client";

/**
 * One-time hand-off of a generated password across a client-side navigation (e.g. "account created, go to its
 * page"). sessionStorage, not app state: it must survive the redirect but never be re-readable after that, and
 * never reach the server.
 *
 * Reading is split into a non-destructive `peekFlash` (safe to call from a useState lazy initializer, which React
 * may invoke more than once per mount) and `clearFlashStorage` (a side effect, called once from an effect).
 */
const KEY = "px_admin_flash";

export interface Flash {
  title: string;
  email: string;
  password: string;
}

export function setFlash(flash: Flash): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(flash));
  } catch {
    /* private mode: the credentials just won't carry over the redirect */
  }
}

export function peekFlash(): Flash | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Flash) : null;
  } catch {
    return null;
  }
}

export function clearFlashStorage(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clean up */
  }
}
