"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface Operator {
  email: string;
}

/** The signed-in operator. Uses the admin session cookie, which the customer app never reads or sets. */
export function useMe() {
  return useQuery({ queryKey: ["admin-me"], queryFn: () => api<Operator>("/api/admin/auth/me"), staleTime: 5 * 60_000 });
}
