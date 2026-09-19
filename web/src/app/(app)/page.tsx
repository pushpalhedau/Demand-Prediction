"use client";

import { PageHeader } from "@/components/data/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Glance } from "@/features/overview/glance";
import { Recommendations } from "@/features/overview/recommendations";
import { usePresentation } from "@/lib/session";

export default function OverviewPage() {
  const { t } = usePresentation();
  return (
    <>
      <PageHeader title={t("ov.title")} />
      <Tabs defaultValue="glance" className="gap-6">
        <TabsList>
          <TabsTrigger value="glance">{t("ov.tab_glance")}</TabsTrigger>
          <TabsTrigger value="recs">{t("ov.tab_recs")}</TabsTrigger>
        </TabsList>
        <TabsContent value="glance">
          <Glance />
        </TabsContent>
        <TabsContent value="recs">
          <Recommendations />
        </TabsContent>
      </Tabs>
    </>
  );
}
