"use client";

import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePresentation } from "@/lib/session";
import { LeadScoring } from "./lead-scoring";
import { Retention } from "./retention";

type View = "retention" | "lead";

export function CustomersPage() {
  const { t } = usePresentation();
  const [view, setView] = useState<View>("retention");
  const nav = (
    <Tabs value={view} onValueChange={(v) => setView(v as View)}>
      <TabsList variant="line" className="h-auto gap-6 border-b p-0" aria-label={t("tab.customers")}>
        <TabsTrigger value="retention" className="flex-none px-0 pb-2.5">{t("cu.tab.retention")}</TabsTrigger>
        <TabsTrigger value="lead" className="flex-none px-0 pb-2.5">{t("cu.tab.lead")}</TabsTrigger>
      </TabsList>
    </Tabs>
  );
  return view === "retention" ? <Retention nav={nav} /> : <LeadScoring nav={nav} />;
}
