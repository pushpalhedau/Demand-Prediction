"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { DataTable, type Column } from "@/admin/components/data/data-table";
import { EmptyState, ErrorState } from "@/admin/components/data/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/admin/lib/api";
import { formatDateTime } from "@/admin/lib/format";
import type { Job, JobStatus } from "@/admin/lib/types";

const ACTIVE = new Set(["queued", "running"]);

export function HistoryTab({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const [activeJob, setActiveJob] = useState<string | null>(null);

  const retrain = useMutation({
    mutationFn: () => api<{ job_id: string }>(`/api/admin/accounts/${slug}/retrain`, { method: "POST" }),
    onSuccess: (r) => setActiveJob(r.job_id),
  });

  const job = useQuery({
    queryKey: ["admin-job", slug, activeJob],
    queryFn: () => api<JobStatus>(`/api/admin/accounts/${slug}/jobs/${activeJob}`),
    enabled: Boolean(activeJob),
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 1500 : false),
  });

  const finished = job.data && !ACTIVE.has(job.data.status);
  useEffect(() => {
    if (!finished) return;
    // The job just finished: refresh the account summary and the jobs list once.
    queryClient.invalidateQueries({ queryKey: ["admin-account", slug] });
    queryClient.invalidateQueries({ queryKey: ["admin-jobs", slug] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished]);

  const jobs = useQuery({ queryKey: ["admin-jobs", slug], queryFn: () => api<Job[]>(`/api/admin/accounts/${slug}/jobs`) });

  const columns: Column<Job>[] = [
    { key: "when", header: "When", cell: (j) => formatDateTime(j.created_at), sort: (j) => j.created_at },
    { key: "kind", header: "Kind", cell: (j) => (j.kind === "retrain" ? "Retrain" : "Import") },
    { key: "status", header: "Status", cell: (j) => <span className="capitalize">{j.status}</span> },
    { key: "by", header: "By", cell: (j) => j.created_by ?? "–" },
    { key: "loaded", header: "Loaded", cell: (j) => Object.entries(j.loaded).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(", ") || "–" },
    { key: "message", header: "Message", cell: (j) => j.message || j.notes.join(" | ") || "–" },
  ];

  return (
    <div className="space-y-6">
      {activeJob && job.data ? (
        <div className="space-y-2">
          {ACTIVE.has(job.data.status) ? (
            <>
              <Progress value={job.data.progress * 100} />
              <p className="text-muted-foreground text-sm">{job.data.stage || "Working"}</p>
            </>
          ) : job.data.status === "succeeded" ? (
            <Alert>
              <AlertDescription>
                Done.
                {(job.data.report?.notes ?? []).map((n) => (
                  <span key={n} className="mt-1 block">{n}</span>
                ))}
              </AlertDescription>
            </Alert>
          ) : (
            <ErrorState message={job.data.message || "Failed."} />
          )}
        </div>
      ) : (
        <Button onClick={() => retrain.mutate()} disabled={retrain.isPending}>
          {retrain.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Retrain models now
        </Button>
      )}
      {retrain.isError && <ErrorState message={retrain.error instanceof ApiError ? retrain.error.message : "Could not start retraining."} />}

      {jobs.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : jobs.isError ? (
        <ErrorState message={jobs.error.message} />
      ) : jobs.data.length === 0 ? (
        <EmptyState title="No imports or retrains yet." />
      ) : (
        <DataTable columns={columns} rows={jobs.data} rowKey={(j) => j.id} initialSort={{ key: "when", dir: "desc" }} />
      )}
    </div>
  );
}
