"use client";

import { PageHeader } from "@/components/data/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePresentation } from "@/lib/session";
import { LeadScoring } from "./lead-scoring";
import { Retention } from "./retention";

export function CustomersPage() {
  const { t } = usePresentation();
  return (
    <>
      <PageHeader title={t("tab.customers")} description={t("cu.subtitle")} />
      <Tabs defaultValue="retention" className="gap-6">
        <TabsList>
          <TabsTrigger value="retention">{t("cu.tab.retention")}</TabsTrigger>
          <TabsTrigger value="lead">{t("cu.tab.lead")}</TabsTrigger>
        </TabsList>
        <TabsContent value="retention">
          <Retention />
        </TabsContent>
        <TabsContent value="lead">
          <LeadScoring />
        </TabsContent>
      </Tabs>
    </>
  );
}
