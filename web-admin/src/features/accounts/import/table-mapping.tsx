"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, api } from "@/lib/api";
import type { FieldDef, MappingProposal, TableMapping, TableName, Transform } from "@/lib/types";
import { unitLabel, type UnitOption } from "./unit-options";

const NOT_MAPPED = "(not mapped)";
const CONFIDENCE_LABEL: Record<string, string> = {
  exact: "exact match",
  converted: "unit match",
  alias: "known synonym",
  fuzzy: "check this guess",
  saved: "saved from last import",
};

interface Row {
  field: FieldDef;
  source: string;
  transform: Transform;
  how: string;
}

export function TableMappingSection({
  slug,
  jobId,
  table,
  fields,
  unitOptions,
  onChange,
}: {
  slug: string;
  jobId: string;
  table: TableName;
  fields: FieldDef[];
  unitOptions: UnitOption[];
  onChange: (table: TableName, mapping: TableMapping, meta: { missingRequired: string[]; imperialHint: boolean }) => void;
}) {
  const query = useQuery({
    queryKey: ["import-mapping", slug, jobId, table],
    queryFn: () => api<MappingProposal>(`/api/admin/accounts/${slug}/imports/${jobId}/${table}/mapping`),
  });
  const [rows, setRows] = useState<Row[] | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (!query.data || initialized.current) return;
    initialized.current = true;
    const { proposal, saved } = query.data;
    setRows(
      fields.map((field) => {
        if (saved) {
          const c = saved[field.name];
          return { field, source: c ? c.source : NOT_MAPPED, transform: c ? c.transform : null, how: c ? "saved" : "" };
        }
        const c = proposal[field.name];
        return { field, source: c ? c.source : NOT_MAPPED, transform: c ? c.transform : null, how: c ? c.confidence : "" };
      }),
    );
  }, [query.data, fields]);

  useEffect(() => {
    if (!rows || !query.data) return;
    const columns: TableMapping["columns"] = {};
    for (const r of rows) {
      if (r.source !== NOT_MAPPED) columns[r.field.name] = { source: r.source, transform: r.transform };
    }
    const missingRequired = fields.filter((f) => f.required && !columns[f.name]).map((f) => f.name);
    onChange(table, { columns, extras: true }, { missingRequired, imperialHint: query.data.imperial_hint });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  if (query.isPending || !rows) return <Skeleton className="h-40 w-full" />;
  if (query.isError) {
    return <ErrorState message={query.error instanceof ApiError ? query.error.message : "Could not read that file."} />;
  }

  const columns = query.data.columns;
  const fuzzy = rows.filter((r) => r.how === "fuzzy").map((r) => r.field.name);

  function setRow(name: string, patch: Partial<Row>) {
    setRows((prev) => prev && prev.map((r) => (r.field.name === name ? { ...r, ...patch } : r)));
  }

  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-sm">
        {columns.length} column{columns.length === 1 ? "" : "s"} found. Anything left unmapped is kept as an extra
        field, not lost.
      </p>
      <div className="rounded-lg border">
        <Table>
          <TableHeader className="bg-muted/50">
            <TableRow className="hover:bg-transparent">
              <TableHead className="h-10 text-xs font-medium">Field</TableHead>
              <TableHead className="h-10 text-xs font-medium">Their column</TableHead>
              <TableHead className="h-10 text-xs font-medium">Unit conversion</TableHead>
              <TableHead className="h-10 text-xs font-medium">Match</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.field.name} className="hover:bg-transparent">
                <TableCell className="py-2 text-sm font-medium whitespace-nowrap">
                  {r.field.name}
                  {r.field.required && <span className="text-destructive"> *</span>}
                </TableCell>
                <TableCell className="py-2">
                  <Select value={r.source} onValueChange={(v) => setRow(r.field.name, { source: v })}>
                    <SelectTrigger className="h-8 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NOT_MAPPED}>{NOT_MAPPED}</SelectItem>
                      {columns.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell className="py-2">
                  <Select
                    value={unitLabel(unitOptions, r.transform)}
                    onValueChange={(label) =>
                      setRow(r.field.name, { transform: unitOptions.find((o) => o.label === label)?.transform ?? null })
                    }
                  >
                    <SelectTrigger className="h-8 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {unitOptions.map((o) => (
                        <SelectItem key={o.label} value={o.label}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell className="py-2 text-sm">
                  {r.how && <Badge variant={r.how === "fuzzy" ? "destructive" : "outline"}>{CONFIDENCE_LABEL[r.how] ?? r.how}</Badge>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {fuzzy.length > 0 && (
        <p className="text-sm text-amber-600 dark:text-amber-500">
          Please double-check these guesses (spelling was close but not exact): {fuzzy.join(", ")}
        </p>
      )}
    </div>
  );
}
