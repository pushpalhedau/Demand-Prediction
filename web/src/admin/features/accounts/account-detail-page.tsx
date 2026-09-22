"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CredentialsCard } from "@/admin/components/data/credentials-card";
import { ErrorState } from "@/admin/components/data/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError } from "@/admin/lib/api";
import { clearFlashStorage, peekFlash } from "@/admin/lib/flash";
import type { AccountDetail } from "@/admin/lib/types";
import { AccessTab } from "./tabs/access-tab";
import { HistoryTab } from "./tabs/history-tab";
import { ImportTab } from "./tabs/import-tab";
import { LoginsTab } from "./tabs/logins-tab";
import { SettingsTab } from "./tabs/settings-tab";
import { AccountHeader } from "./account-header";

export function AccountDetailPage({ slug }: { slug: string }) {
  const query = useQuery({ queryKey: ["admin-account", slug], queryFn: () => api<AccountDetail>(`/api/admin/accounts/${slug}`) });
  const [flash, setFlash] = useState(peekFlash);

  useEffect(() => {
    clearFlashStorage();
  }, []);

  if (query.isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404;
    return (
      <div className="space-y-4">
        <ErrorState message={notFound ? "That account no longer exists." : query.error.message} />
        <Button asChild variant="outline" size="sm">
          <Link href="/admin">← All accounts</Link>
        </Button>
      </div>
    );
  }

  const account = query.data;
  return (
    <div className="space-y-8">
      {flash && <CredentialsCard flash={flash} onDismiss={() => setFlash(null)} />}
      <AccountHeader account={account} />
      <Tabs defaultValue="import">
        <TabsList variant="line" className="h-auto gap-6 border-b p-0" aria-label={account.name}>
          <TabsTrigger value="import" className="flex-none px-0 pb-2.5">Import data</TabsTrigger>
          <TabsTrigger value="history" className="flex-none px-0 pb-2.5">History &amp; models</TabsTrigger>
          <TabsTrigger value="logins" className="flex-none px-0 pb-2.5">Logins</TabsTrigger>
          <TabsTrigger value="settings" className="flex-none px-0 pb-2.5">Settings</TabsTrigger>
          <TabsTrigger value="access" className="flex-none px-0 pb-2.5">Access</TabsTrigger>
        </TabsList>
        <TabsContent value="import" className="pt-6">
          <ImportTab slug={account.slug} />
        </TabsContent>
        <TabsContent value="history" className="pt-6">
          <HistoryTab slug={account.slug} />
        </TabsContent>
        <TabsContent value="logins" className="pt-6">
          <LoginsTab slug={account.slug} />
        </TabsContent>
        <TabsContent value="settings" className="pt-6">
          <SettingsTab slug={account.slug} config={account.config} />
        </TabsContent>
        <TabsContent value="access" className="pt-6">
          <AccessTab account={account} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
