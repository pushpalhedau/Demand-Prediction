"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CredentialsCard } from "@/components/data/credentials-card";
import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { clearFlashStorage, peekFlash } from "@/lib/flash";
import { formatDate } from "@/lib/format";
import type { Account } from "@/lib/types";
import { CreateAccountDialog } from "./create-account-dialog";

export function AccountsPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["admin-accounts"], queryFn: () => api<Account[]>("/api/admin/accounts") });
  const [flash, setFlashState] = useState(peekFlash);

  useEffect(() => {
    clearFlashStorage();
  }, []);

  const columns: Column<Account>[] = [
    { key: "name", header: "Name", cell: (a) => <span className="font-medium">{a.name}</span>, sort: (a) => a.name },
    { key: "slug", header: "Id", cell: (a) => <code className="text-muted-foreground text-xs">{a.slug}</code>, sort: (a) => a.slug },
    {
      key: "status",
      header: "Status",
      cell: (a) => <Badge variant={a.status === "active" ? "secondary" : "destructive"}>{a.status === "active" ? "Active" : "Suspended"}</Badge>,
      sort: (a) => a.status,
    },
    { key: "currency", header: "Currency", cell: (a) => a.config.currency ?? "–", sort: (a) => a.config.currency },
    { key: "language", header: "Language", cell: (a) => a.config.language ?? "–", sort: (a) => a.config.language },
    { key: "created", header: "Created", cell: (a) => formatDate(a.created_at), sort: (a) => a.created_at },
  ];

  return (
    <>
      <PageHeader eyebrow="Operator console" title="Accounts" description="Create customer accounts, load their data, train their models." actions={<CreateAccountDialog />} />
      {flash && <CredentialsCard flash={flash} onDismiss={() => setFlashState(null)} />}

      {query.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} reference={query.error instanceof ApiError ? query.error.reference : undefined} />
      ) : query.data.length === 0 ? (
        <EmptyState title="No accounts yet">Create the first one above.</EmptyState>
      ) : (
        <DataTable
          columns={columns}
          rows={query.data}
          rowKey={(a) => a.id}
          initialSort={{ key: "created", dir: "desc" }}
          onRowClick={(a) => router.push(`/accounts/${a.slug}`)}
        />
      )}
    </>
  );
}
