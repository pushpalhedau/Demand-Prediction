"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Section } from "@/admin/components/data/section";
import { ErrorState } from "@/admin/components/data/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, apiUpload } from "@/admin/lib/api";
import type { DryRunReport, ImportSchema, JobStatus, TableMapping, TableName } from "@/admin/lib/types";
import { TableMappingSection } from "../import/table-mapping";
import { buildUnitOptions } from "../import/unit-options";

const TABLE_HELP: Record<TableName, string> = {
  sales: "Required. One row per sale: a date, a price or revenue, and ideally brand, model, dealer and region.",
  dealers: "Optional. Their stores. Built from the sales file if skipped.",
  vehicles: "Optional. Their model catalogue. Built from the sales file if skipped.",
  customers: "Optional. Unlocks Customer Intelligence.",
  inventory: "Optional. Stock snapshots. Unlocks Inventory & Placement.",
  external_factors: "Optional. Monthly fuel prices, rates, indices. Sharpens the forecast.",
};

const ACTIVE = new Set(["queued", "running"]);

function tableLabel(table: TableName): string {
  return table.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function downloadTemplate(table: TableName, fields: ImportSchema["tables"][TableName]) {
  const header = fields.filter((f) => !f.derived).map((f) => f.name).join(",");
  const blob = new Blob([header + "\n"], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${table}_template.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ImportTab({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const schema = useQuery({ queryKey: ["import-schema"], queryFn: () => api<ImportSchema>("/api/admin/imports/schema"), staleTime: Infinity });

  const [jobId, setJobId] = useState(() => crypto.randomUUID());
  const [uploadVersion, setUploadVersion] = useState<Partial<Record<TableName, number>>>({});
  const [uploading, setUploading] = useState<TableName | null>(null);
  const [uploadErrors, setUploadErrors] = useState<Partial<Record<TableName, string>>>({});
  const [uploaded, setUploaded] = useState<Set<TableName>>(new Set());
  const [mappings, setMappings] = useState<Partial<Record<TableName, TableMapping>>>({});
  const [missingRequired, setMissingRequired] = useState<Partial<Record<TableName, string[]>>>({});
  const [imperialHint, setImperialHint] = useState<Partial<Record<TableName, boolean>>>({});
  const [dryRuns, setDryRuns] = useState<Partial<Record<TableName, DryRunReport>>>({});
  const [dryRunErrors, setDryRunErrors] = useState<Partial<Record<TableName, string>>>({});
  const [checking, setChecking] = useState(false);
  const [dayfirst, setDayfirst] = useState(false);
  const [decimal, setDecimal] = useState<"." | ",">(".");
  const [distance, setDistance] = useState<"km" | "mi">("km");
  const [distanceTouched, setDistanceTouched] = useState(false);
  const [replace, setReplace] = useState(true);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const anyImperial = Object.values(imperialHint).some(Boolean);
  useEffect(() => {
    if (anyImperial && !distanceTouched) setDistance("mi");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anyImperial]);

  const job = useQuery({
    queryKey: ["admin-job", slug, activeJobId],
    queryFn: () => api<JobStatus>(`/api/admin/accounts/${slug}/jobs/${activeJobId}`),
    enabled: Boolean(activeJobId),
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 1500 : false),
  });
  const finished = job.data && !ACTIVE.has(job.data.status);
  useEffect(() => {
    if (!finished) return;
    queryClient.invalidateQueries({ queryKey: ["admin-account", slug] });
    queryClient.invalidateQueries({ queryKey: ["admin-jobs", slug] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished]);

  const start = useMutation({
    mutationFn: () =>
      api<{ job_id: string }>(`/api/admin/accounts/${slug}/imports/${jobId}/start`, {
        method: "POST",
        body: {
          tables: orderedUploaded(),
          mappings,
          units: { distance },
          dayfirst,
          decimal,
          replace,
          train: true,
        },
      }),
    onSuccess: (r) => setActiveJobId(r.job_id),
  });

  function orderedUploaded(): TableName[] {
    return (schema.data?.load_order ?? []).filter((t) => uploaded.has(t));
  }

  async function handleFile(table: TableName, file: File | undefined) {
    if (!file) return;
    setUploading(table);
    setUploadErrors((e) => ({ ...e, [table]: undefined }));
    try {
      await apiUpload(`/api/admin/accounts/${slug}/imports/${jobId}/files/${table}`, file);
      setUploaded((s) => new Set(s).add(table));
      setUploadVersion((v) => ({ ...v, [table]: (v[table] ?? 0) + 1 }));
      setDryRuns((d) => ({ ...d, [table]: undefined }));
    } catch (err) {
      setUploadErrors((e) => ({ ...e, [table]: err instanceof ApiError ? err.message : "Upload failed." }));
    } finally {
      setUploading(null);
    }
  }

  function handleMappingChange(table: TableName, mapping: TableMapping, meta: { missingRequired: string[]; imperialHint: boolean }) {
    setMappings((prev) => ({ ...prev, [table]: mapping }));
    setMissingRequired((prev) => ({ ...prev, [table]: meta.missingRequired }));
    setImperialHint((prev) => ({ ...prev, [table]: meta.imperialHint }));
  }

  async function checkData() {
    setChecking(true);
    const results: Partial<Record<TableName, DryRunReport>> = {};
    const errors: Partial<Record<TableName, string>> = {};
    await Promise.all(
      orderedUploaded().map(async (table) => {
        const mapping = mappings[table];
        if (!mapping) return;
        try {
          results[table] = await api<DryRunReport>(`/api/admin/accounts/${slug}/imports/${jobId}/${table}/dry-run`, {
            method: "POST",
            body: { mapping, units: { distance }, dayfirst, decimal },
          });
        } catch (err) {
          errors[table] = err instanceof ApiError ? err.message : `${table}: could not check this file.`;
        }
      }),
    );
    setDryRuns(results);
    setDryRunErrors(errors);
    setChecking(false);
  }

  function reset() {
    setJobId(crypto.randomUUID());
    setUploaded(new Set());
    setUploadVersion({});
    setUploadErrors({});
    setMappings({});
    setMissingRequired({});
    setImperialHint({});
    setDryRuns({});
    setDryRunErrors({});
    setDistanceTouched(false);
    setActiveJobId(null);
  }

  if (schema.isPending) return <Skeleton className="h-64 w-full" />;
  if (schema.isError) return <ErrorState message="Could not load the import wizard." />;

  const unitOptions = buildUnitOptions(schema.data.constants);

  if (activeJobId && job.data) {
    return (
      <div className="max-w-2xl space-y-3">
        {ACTIVE.has(job.data.status) ? (
          <>
            <Progress value={job.data.progress * 100} />
            <p className="text-muted-foreground text-sm">{job.data.stage || "Working"}</p>
            <p className="text-muted-foreground text-xs">You can leave this tab open. Large files take a few minutes.</p>
          </>
        ) : job.data.status === "succeeded" ? (
          <Alert>
            <CheckCircle2 />
            <AlertTitle>Import complete. The account&apos;s dashboards are live.</AlertTitle>
            <AlertDescription>
              {Object.entries(job.data.report?.loaded ?? {}).map(([table, n]) => (
                <span key={table} className="mt-1 block">{table}: {n.toLocaleString()} rows</span>
              ))}
              {(job.data.report?.notes ?? []).map((n) => (
                <span key={n} className="mt-1 block">{n}</span>
              ))}
              <Button size="sm" className="mt-3" onClick={reset}>Done</Button>
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-3">
            <ErrorState message={job.data.message || "The import failed."} />
            <Button size="sm" variant="outline" onClick={() => setActiveJobId(null)}>
              Go back and fix
            </Button>
          </div>
        )}
      </div>
    );
  }

  const hasSales = uploaded.has("sales");
  const canImport = hasSales && orderedUploaded().every((t) => mappings[t] && (missingRequired[t] ?? []).length === 0);

  return (
    <div className="space-y-8">
      <Section title="1. Upload the customer's files" description="CSV files, up to 500 MB each. Only the sales file is required.">
        <div className="grid gap-4 sm:grid-cols-2">
          {schema.data.load_order.map((table) => (
            <div key={table} className="space-y-1.5">
              <Label htmlFor={`up-${table}`}>
                {tableLabel(table)}
                {table === "sales" && <span className="text-destructive"> *</span>}
              </Label>
              <div className="flex items-center gap-2">
                <Input id={`up-${table}`} type="file" accept=".csv" disabled={uploading === table} onChange={(e) => handleFile(table, e.target.files?.[0])} />
                {uploading === table && <Loader2 className="size-4 shrink-0 animate-spin" />}
                {uploaded.has(table) && uploading !== table && <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />}
              </div>
              <p className="text-muted-foreground text-xs">{TABLE_HELP[table]}</p>
              {uploadErrors[table] && <p className="text-destructive text-xs">{uploadErrors[table]}</p>}
              <Button type="button" variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => downloadTemplate(table, schema.data.tables[table])}>
                <Download className="size-3" /> Template CSV
              </Button>
            </div>
          ))}
        </div>
      </Section>

      {!hasSales ? (
        <p className="text-muted-foreground text-sm">Upload the sales file to continue.</p>
      ) : (
        <>
          <Section title="2. Check the column matching">
            <div className="space-y-6">
              {orderedUploaded().map((table) => (
                <div key={`${table}-${uploadVersion[table] ?? 0}`} className="space-y-2 border-b pb-6 last:border-b-0 last:pb-0">
                  <h3 className="text-sm font-semibold">{tableLabel(table)}</h3>
                  <TableMappingSection
                    slug={slug}
                    jobId={jobId}
                    table={table}
                    fields={schema.data.tables[table]}
                    unitOptions={unitOptions}
                    onChange={handleMappingChange}
                  />
                </div>
              ))}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="space-y-1.5">
                  <Label>Dates are written</Label>
                  <Select value={dayfirst ? "dmy" : "auto"} onValueChange={(v) => setDayfirst(v === "dmy")}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Year-Month-Day (or auto)</SelectItem>
                      <SelectItem value="dmy">Day/Month/Year</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Decimal separator</Label>
                  <Select value={decimal} onValueChange={(v) => setDecimal(v as typeof decimal)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value=".">. (1,234.50)</SelectItem>
                      <SelectItem value=",">, (1.234,50)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Distances (mileage) are in</Label>
                  <Select value={distance} onValueChange={(v) => { setDistance(v as typeof distance); setDistanceTouched(true); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="km">km</SelectItem>
                      <SelectItem value="mi">miles</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Import mode</Label>
                  <Select value={replace ? "replace" : "add"} onValueChange={(v) => setReplace(v === "replace")}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="replace">Replace all their data</SelectItem>
                      <SelectItem value="add">Add to their existing data</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button type="button" variant="outline" onClick={checkData} disabled={checking}>
                {checking && <Loader2 className="animate-spin" />} Check the data
              </Button>
              {orderedUploaded().map((table) => {
                const report = dryRuns[table];
                const error = dryRunErrors[table];
                if (!report && !error) return null;
                if (error) return <ErrorState key={table} message={error} />;
                const bad = report!.coercion_failures;
                return (
                  <Alert key={table}>
                    <AlertDescription>
                      {table}: looks good ({report!.rows_out.toLocaleString()} of {report!.rows_in.toLocaleString()} sample rows usable)
                      {Object.keys(bad).length > 0 && (
                        <span className="mt-1 block">
                          values that could not be read: {Object.entries(bad).map(([k, v]) => `${k} (${v})`).join(", ")}
                        </span>
                      )}
                      {report!.warnings.map((w) => (
                        <span key={w} className="text-muted-foreground mt-1 block text-xs">{w}</span>
                      ))}
                    </AlertDescription>
                  </Alert>
                );
              })}
            </div>
          </Section>

          <Section title="3. Import" description="Models retrain automatically once the data is loaded.">
            {start.isError && (
              <ErrorState message={start.error instanceof ApiError ? start.error.message : "Could not start the import."} />
            )}
            <Button onClick={() => start.mutate()} disabled={!canImport || start.isPending} className="mt-3">
              {start.isPending && <Loader2 className="animate-spin" />} Import and train
            </Button>
          </Section>
        </>
      )}
    </div>
  );
}
