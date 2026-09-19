"use client";

import { useState } from "react";
import { Tabs } from "@/components/ui/primitives";
import { Glance } from "@/features/overview/Glance";
import { Recommendations } from "@/features/overview/Recommendations";
import { usePresentation } from "@/lib/session";

export default function OverviewPage() {
  const { t } = usePresentation();
  const [view, setView] = useState<"glance" | "recs">("glance");

  return (
    <div>
      <h1 className="gradient-text mb-4 text-2xl font-bold">{t("ov.title")}</h1>
      <Tabs
        value={view}
        onChange={setView}
        tabs={[
          { id: "glance", label: t("ov.tab_glance") },
          { id: "recs", label: t("ov.tab_recs") },
        ]}
      />
      <div className="mt-6">{view === "glance" ? <Glance /> : <Recommendations />}</div>
    </div>
  );
}
