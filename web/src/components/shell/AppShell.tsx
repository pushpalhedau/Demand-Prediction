"use client";

import clsx from "clsx";
import {
  BarChart3,
  Boxes,
  LogOut,
  Menu,
  MessageSquareQuote,
  Store,
  TrendingUp,
  Users,
  X,
  LayoutGrid,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";
import { useMe, usePresentation } from "@/lib/session";
import type { Lang } from "@/lib/types";
import { Notice, Skeleton } from "@/components/ui/primitives";
import { FilterBar } from "./FilterBar";

export const TAB_ROUTES: Record<string, { href: string; icon: LucideIcon }> = {
  "tab.overview": { href: "/", icon: BarChart3 },
  "tab.forecasting": { href: "/forecasting", icon: TrendingUp },
  "tab.comparison": { href: "/comparison", icon: LayoutGrid },
  "tab.regional": { href: "/regional", icon: Store },
  "tab.customers": { href: "/customers", icon: Users },
  "tab.inventory": { href: "/inventory", icon: Boxes },
  "tab.sentiment": { href: "/sentiment", icon: MessageSquareQuote },
};

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { t, lang, setLang } = usePresentation();
  const { data: me, error, isPending } = useMe();
  const [open, setOpen] = useState(false);

  const unauthenticated = error instanceof ApiError && error.status === 401;
  useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);

  async function signOut() {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    queryClient.clear();
    router.replace("/login");
  }

  if (isPending || unauthenticated) {
    return (
      <div className="p-8">
        <Skeleton className="h-10 w-64" />
      </div>
    );
  }
  if (error || !me) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <Notice>Could not load your workspace. Please refresh, or contact support if this continues.</Notice>
      </div>
    );
  }

  const account = (
    <div className="mt-6 space-y-3 border-t border-line pt-4 text-sm">
      <div>
        <p className="font-medium">{me.organisation.name}</p>
        <p className="truncate text-xs text-muted">{me.user.email}</p>
      </div>
      <label className="block text-xs text-muted">
        {t("app.language")}
        <select
          value={lang}
          onChange={(e) => setLang(e.target.value as Lang)}
          className="mt-1 block w-full rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-sm text-ink"
        >
          {Object.entries(LANGUAGES).map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <button onClick={signOut} className="flex items-center gap-2 text-muted hover:text-ink">
        <LogOut size={16} aria-hidden /> Sign out
      </button>
    </div>
  );

  if (!me.ready) {
    return (
      <main className="mx-auto max-w-xl p-8">
        <h1 className="gradient-text text-2xl font-bold">Your account is being set up</h1>
        <p className="mt-3 text-muted">
          Your data is being prepared. Your dashboards will appear here as soon as it is ready. If this takes longer
          than expected, please contact support.
        </p>
        {account}
      </main>
    );
  }

  const nav = me.tabs
    .map((key) => ({ key, ...TAB_ROUTES[key] }))
    .filter((item): item is { key: string; href: string; icon: LucideIcon } => Boolean(item.href));

  const sidebar = (
    <div className="flex h-full flex-col overflow-y-auto p-5">
      <p className="gradient-text text-2xl font-bold">PredictaX</p>
      <nav aria-label="Main" className="mt-6 space-y-1">
        {nav.map(({ key, href, icon: Icon }) => {
          const current = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={key}
              href={href}
              aria-current={current ? "page" : undefined}
              onClick={() => setOpen(false)}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                current ? "bg-brand/20 font-semibold text-ink" : "text-muted hover:bg-white/5 hover:text-ink",
              )}
            >
              <Icon size={17} aria-hidden /> {t(key)}
            </Link>
          );
        })}
      </nav>
      <div className="mt-6 border-t border-line pt-5">
        <Suspense fallback={null}>
          <FilterBar regionLabel={me.organisation.region_label} dataRange={me.data_range} />
        </Suspense>
      </div>
      {account}
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[18rem_1fr]">
      <header className="flex items-center justify-between border-b border-line px-4 py-3 lg:hidden">
        <span className="gradient-text text-lg font-bold">PredictaX</span>
        <button onClick={() => setOpen((v) => !v)} aria-label="Toggle menu" aria-expanded={open}>
          {open ? <X /> : <Menu />}
        </button>
      </header>
      <aside
        className={clsx(
          "border-line bg-panel/60 lg:sticky lg:top-0 lg:block lg:h-screen lg:border-r",
          open ? "block border-b" : "hidden",
        )}
      >
        {sidebar}
      </aside>
      <main className="min-w-0 p-4 sm:p-8">{children}</main>
    </div>
  );
}
