"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/**
 * The global dashboard filters live in the URL, so a view can be bookmarked or shared and the back button works.
 * Empty means "all"; the dates default to the account's whole sales history on the server.
 */
export interface Filters {
  from: string;
  to: string;
  region: string;
  city: string;
  brand: string;
  category: string;
  fuel: string;
}

const KEYS: (keyof Filters)[] = ["from", "to", "region", "city", "brand", "category", "fuel"];

/** Query-string names the API expects. */
const API_NAMES: Record<keyof Filters, string> = {
  from: "start_date",
  to: "end_date",
  region: "region",
  city: "city",
  brand: "brand",
  category: "vehicle_category",
  fuel: "fuel_type",
};

export function useFilters() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters = useMemo(() => {
    const value = {} as Filters;
    for (const key of KEYS) value[key] = search.get(key) ?? "";
    return value;
  }, [search]);

  const apiParams = useMemo(() => {
    const params: Record<string, string> = {};
    for (const key of KEYS) if (filters[key]) params[API_NAMES[key]] = filters[key];
    return params;
  }, [filters]);

  const update = useCallback(
    (patch: Partial<Filters>) => {
      const next = new URLSearchParams(search.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      // Changing the region invalidates a city picked under the old one.
      if ("region" in patch && !("city" in patch)) next.delete("city");
      const text = next.toString();
      router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
    },
    [search, router, pathname],
  );

  const reset = useCallback(() => router.replace(pathname, { scroll: false }), [router, pathname]);
  const active = KEYS.some((k) => filters[k]);

  return { filters, apiParams, update, reset, active };
}
