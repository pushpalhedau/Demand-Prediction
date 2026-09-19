"use client";

import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Glance } from "@/features/overview/glance";
import { Recommendations } from "@/features/overview/recommendations";
import { usePresentation } from "@/lib/session";

export default function OverviewPage() {
  const { t } = usePresentation();
  const [view, setView] = useState<"glance" | "recs">("glance");
  const nav = (
    <Tabs value={view} onValueChange={(v) => setView(v as "glance" | "recs")}>
      <TabsList variant="line" className="h-auto gap-6 border-b p-0" aria-label={t("ov.title")}>
        <TabsTrigger value="glance" className="flex-none px-0 pb-2.5">{t("ov.tab_glance")}</TabsTrigger>
        <TabsTrigger value="recs" className="flex-none px-0 pb-2.5">{t("ov.tab_recs")}</TabsTrigger>
      </TabsList>
    </Tabs>
  );
  return view === "glance" ? <Glance nav={nav} /> : <Recommendations nav={nav} />;
}
