"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { PanelSkeleton } from "./chart-card";
import { ErrorState } from "./states";

/** Loading, error and data in one place, so every dashboard handles a slow or failed request the same way. */
export function QueryBoundary<T>({
  query,
  skeleton,
  errorMessage,
  children,
}: {
  query: UseQueryResult<T>;
  skeleton?: ReactNode;
  errorMessage?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <>{skeleton ?? <PanelSkeleton height={320} />}</>;
  if (query.isError) {
    const error = query.error;
    return <ErrorState message={errorMessage ?? error.message} reference={error instanceof ApiError ? error.reference : undefined} />;
  }
  return <>{children(query.data)}</>;
}
