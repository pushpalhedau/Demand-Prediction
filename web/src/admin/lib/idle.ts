"use client";

import { useEffect, useRef } from "react";

const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // an unattended console signs itself out, same as the classic app
const ACTIVITY_EVENTS = ["mousedown", "keydown", "scroll", "touchstart"] as const;

/** Calls `onIdle` once the operator has not touched the page for `IDLE_TIMEOUT_MS`. */
export function useIdleLogout(onIdle: () => void): void {
  const callback = useRef(onIdle);
  useEffect(() => {
    callback.current = onIdle;
  }, [onIdle]);

  useEffect(() => {
    let lastActive = Date.now();
    const mark = () => {
      lastActive = Date.now();
    };
    ACTIVITY_EVENTS.forEach((event) => window.addEventListener(event, mark, { passive: true }));
    const timer = window.setInterval(() => {
      if (Date.now() - lastActive > IDLE_TIMEOUT_MS) callback.current();
    }, 30_000);
    return () => {
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, mark));
      window.clearInterval(timer);
    };
  }, []);
}
