"use client";

import { notFound, useParams } from "next/navigation";
import { EmptyState } from "@/components/data/states";
import { PageHeading } from "@/components/data/page-heading";
import { NAV } from "@/lib/nav";
import { usePresentation } from "@/lib/session";

/** A dashboard the API lists for the account but this app has no page for yet. */
export default function PendingTab() {
  const { tab } = useParams<{ tab: string }>();
  const { t } = usePresentation();
  const item = NAV.find((n) => n.href === `/${tab}`);
  if (!item) notFound();
  return (
    <>
      <PageHeading eyebrow={t(item.key)} headline={t(item.key)} />
      <EmptyState title="Not available yet">This dashboard is being moved to the new interface.</EmptyState>
    </>
  );
}
