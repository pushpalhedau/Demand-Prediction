"use client";

import { notFound, useParams } from "next/navigation";
import { TAB_ROUTES } from "@/components/shell/AppShell";
import { Notice } from "@/components/ui/primitives";
import { usePresentation } from "@/lib/session";

const LEGACY_URL = process.env.NEXT_PUBLIC_LEGACY_URL;

/** Tabs that have not moved to the new frontend yet. They stay available in the classic app meanwhile. */
export default function PendingTab() {
  const { tab } = useParams<{ tab: string }>();
  const { t } = usePresentation();
  const key = Object.keys(TAB_ROUTES).find((k) => TAB_ROUTES[k]?.href === `/${tab}`);
  if (!key) notFound();

  return (
    <div className="max-w-2xl">
      <h1 className="gradient-text text-2xl font-bold">{t(key)}</h1>
      <div className="mt-4">
        <Notice>
          This view is moving to the new dashboard and is not available here yet.
          {LEGACY_URL && (
            <>
              {" "}
              Meanwhile you can use it in the{" "}
              <a className="text-accent underline" href={LEGACY_URL}>
                classic dashboard
              </a>
              .
            </>
          )}
        </Notice>
      </div>
    </div>
  );
}
