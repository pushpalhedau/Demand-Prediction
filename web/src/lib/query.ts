"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { api } from "./api";
import { useFilters } from "./filters";
import { usePresentation } from "./session";

type Params = Record<string, string | number | null | undefined>;

/**
 * Query a dashboard endpoint scoped by the global filters. The key carries the filters (and the language, for
 * endpoints whose wording is generated server-side), so a change in either refetches.
 */
export function useDashboardQuery<T>(
  name: string,
  path: string,
  options: { params?: Params; serverText?: boolean; enabled?: boolean } & Partial<Pick<UseQueryOptions<T>, "staleTime">> = {},
) {
  const { apiParams } = useFilters();
  const { lang } = usePresentation();
  const { params, serverText, enabled, staleTime } = options;
  return useQuery<T>({
    queryKey: [name, apiParams, params ?? null, serverText ? lang : null],
    queryFn: () => api<T>(path, { params: { ...apiParams, ...params } }),
    enabled,
    staleTime,
  });
}
