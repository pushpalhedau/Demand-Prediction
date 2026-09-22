"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  /** Provide to make the column sortable. */
  sort?: (row: T) => number | string | null | undefined;
  align?: "left" | "right";
  className?: string;
}

/** A sortable table over rows already in memory. Numbers align right and use tabular figures. */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  initialSort,
  onRowClick,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  initialSort?: { key: string; dir: "asc" | "desc" };
  onRowClick?: (row: T) => void;
}) {
  const [sort, setSort] = useState(initialSort ?? null);

  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sort?.key);
    if (!sort || !column?.sort) return rows;
    const value = column.sort;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = value(a);
      const y = value(b);
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x < y ? -1 : 1) * dir;
    });
  }, [rows, columns, sort]);

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow className="hover:bg-transparent">
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const Icon = !active ? ChevronsUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
              return (
                <TableHead
                  key={c.key}
                  className={cn("h-10 text-xs font-medium whitespace-nowrap", c.align === "right" && "text-right", c.className)}
                  aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
                >
                  {c.sort ? (
                    <button
                      type="button"
                      className={cn("hover:text-foreground inline-flex items-center gap-1", c.align === "right" && "flex-row-reverse")}
                      onClick={() => setSort(active && sort.dir === "desc" ? { key: c.key, dir: "asc" } : { key: c.key, dir: "desc" })}
                    >
                      {c.header}
                      <Icon className={cn("size-3.5", active ? "text-foreground" : "text-muted-foreground/60")} aria-hidden />
                    </button>
                  ) : (
                    c.header
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row, i) => (
            <TableRow
              key={rowKey(row, i)}
              onClick={onRowClick && (() => onRowClick(row))}
              className={cn(onRowClick && "cursor-pointer")}
            >
              {columns.map((c) => (
                <TableCell key={c.key} className={cn("py-2.5 text-sm", c.align === "right" && "tabular text-right", c.className)}>
                  {c.cell(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
