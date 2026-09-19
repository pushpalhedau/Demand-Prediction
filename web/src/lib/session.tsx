"use client";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { createContext, useContext, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { ApiError, api, setApiLanguage } from "./api";
import { formatCompact, formatMoney, formatNumber, formatPercent } from "./format";
import { isLang, translate, translateValue } from "./i18n";
import type { Lang, Me } from "./types";

const LANG_KEY = "px_lang";

interface Presentation {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  tv: (value: string) => string;
}

const PresentationContext = createContext<Presentation | null>(null);

// The saved language choice lives in localStorage; useSyncExternalStore keeps server and client renders consistent.
const listeners = new Set<() => void>();
function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", callback);
  };
}
function storedLang(): Lang | null {
  try {
    const value = window.localStorage.getItem(LANG_KEY);
    return isLang(value) ? value : null;
  } catch {
    return null;
  }
}
function saveLang(lang: Lang): void {
  try {
    window.localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* private mode: the choice just lasts until the next visit */
  }
  listeners.forEach((notify) => notify());
}

/** UI language: the user's saved choice, else their organisation's default, else English. */
function PresentationProvider({ children }: { children: ReactNode }) {
  const saved = useSyncExternalStore(subscribe, storedLang, () => null);
  const { data } = useMe();
  const lang: Lang = saved ?? data?.organisation.language ?? "en";
  // Set during render (not in an effect) so requests fired by child effects already carry the right language.
  setApiLanguage(lang);

  const value = useMemo<Presentation>(
    () => ({
      lang,
      setLang: saveLang,
      t: (key, vars) => translate(lang, key, vars),
      tv: (v) => translateValue(lang, v),
    }),
    [lang],
  );
  return <PresentationContext.Provider value={value}>{children}</PresentationContext.Provider>;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <PresentationProvider>
          <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
          <Toaster richColors closeButton />
        </PresentationProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export function usePresentation(): Presentation {
  const value = useContext(PresentationContext);
  if (!value) throw new Error("usePresentation must be used inside <Providers>");
  return value;
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/api/me"), staleTime: 5 * 60_000 });
}

/** Number/money/percent formatters bound to the signed-in organisation and the UI language. */
export function useFormat() {
  const { lang } = usePresentation();
  const { data } = useMe();
  const org = data?.organisation ?? { currency_symbol: "€", symbol_position: null };
  return useMemo(
    () => ({
      money: (v: number | null | undefined, compact = true) => formatMoney(v, org, lang, compact),
      num: (v: number | null | undefined, digits = 0) => formatNumber(v, lang, digits),
      compact: (v: number | null | undefined) => formatCompact(v, lang),
      pct: (v: number | null | undefined, digits = 1, signed = false) => formatPercent(v, lang, digits, signed),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [lang, org.currency_symbol, org.symbol_position],
  );
}
