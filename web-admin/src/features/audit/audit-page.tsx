"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { formatDateTime } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

export function AuditPage() {
  const [account, setAccount] = useState("");
  const query = useQuery({
    queryKey: ["admin-audit", account],
    queryFn: () => api<AuditEvent[]>("/api/admin/audit", { params: { limit: 500, account: account || undefined } }),
  });

  const columns: Column<AuditEvent>[] = [
    { key: "at", header: "When", cell: (e) => formatDateTime(e.at), sort: (e) => e.at },
    { key: "actor", header: "Actor", cell: (e) => e.actor, sort: (e) => e.actor },
    { key: "action", header: "Action", cell: (e) => e.action, sort: (e) => e.action },
    { key: "account", header: "Account", cell: (e) => e.account || "–", sort: (e) => e.account },
    {
      key: "outcome",
      header: "Outcome",
      cell: (e) => <Badge variant={e.outcome === "ok" ? "secondary" : "destructive"}>{e.outcome}</Badge>,
      sort: (e) => e.outcome,
    },
    { key: "detail", header: "Detail", cell: (e) => (Object.keys(e.detail).length ? JSON.stringify(e.detail) : "–"), className: "max-w-sm truncate" },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Operator console"
        title="Audit log"
        description="Every operator sign-in, account change, import, retrain and reset. Append-only."
        actions={
          query.data && query.data.length > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                downloadCsv(
                  "audit_log.csv",
                  ["When", "Actor", "Action", "Account", "Outcome", "Detail"],
                  query.data.map((e) => [formatDateTime(e.at), e.actor, e.action, e.account, e.outcome, JSON.stringify(e.detail)]),
                )
              }
            >
              <Download /> Export CSV
            </Button>
          ) : undefined
        }
      />
      <Input placeholder="Filter by account id…" value={account} onChange={(e) => setAccount(e.target.value)} className="max-w-xs" />
      {query.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} reference={query.error instanceof ApiError ? query.error.reference : undefined} />
      ) : query.data.length === 0 ? (
        <EmptyState title="No events." />
      ) : (
        <DataTable columns={columns} rows={query.data} rowKey={(e, i) => `${e.at}-${i}`} initialSort={{ key: "at", dir: "desc" }} />
      )}
    </>
  );
}
