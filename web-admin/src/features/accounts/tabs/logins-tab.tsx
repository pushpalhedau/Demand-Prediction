"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { CredentialsCard } from "@/components/data/credentials-card";
import { DataTable, type Column } from "@/components/data/data-table";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";
import type { Flash } from "@/lib/flash";
import type { CreatedLogin, Login } from "@/lib/types";

export function LoginsTab({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["admin-logins", slug], queryFn: () => api<Login[]>(`/api/admin/accounts/${slug}/logins`) });
  const [flash, setFlash] = useState<Flash | null>(null);
  const [role, setRole] = useState<"tenant_admin" | "tenant_user">("tenant_user");
  const [resetWho, setResetWho] = useState<string>("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-logins", slug] });

  const add = useMutation({
    mutationFn: (body: { email: string; password: string | null; role: string }) => api<CreatedLogin>(`/api/admin/accounts/${slug}/logins`, { method: "POST", body }),
    onSuccess: (created) => {
      setFlash({ title: "Login added.", email: created.email, password: created.password });
      invalidate();
    },
  });

  const reset = useMutation({
    mutationFn: (userId: string) => api<{ password: string }>(`/api/admin/accounts/logins/${userId}/reset-password`, { method: "POST" }),
    onSuccess: (r, userId) => {
      const who = query.data?.find((u) => u.id === userId);
      setFlash({ title: "Password reset.", email: who?.email ?? "", password: r.password });
    },
  });

  const columns: Column<Login>[] = [
    { key: "email", header: "Email", cell: (u) => u.email, sort: (u) => u.email },
    { key: "role", header: "Role", cell: (u) => (u.role === "tenant_admin" ? "Manage" : "View only"), sort: (u) => u.role },
    { key: "last", header: "Last sign-in", cell: (u) => u.last_sign_in, sort: (u) => u.last_sign_in },
    { key: "created", header: "Created", cell: (u) => u.created, sort: (u) => u.created },
  ];

  return (
    <div className="space-y-8">
      {flash && <CredentialsCard flash={flash} onDismiss={() => setFlash(null)} />}

      {query.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} />
      ) : query.data.length === 0 ? (
        <EmptyState title="This account has no logins yet." />
      ) : (
        <DataTable columns={columns} rows={query.data} rowKey={(u) => u.id} initialSort={{ key: "created", dir: "desc" }} />
      )}

      <form
        className="max-w-xl space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          add.mutate({ email: String(data.get("email") ?? "").trim(), password: String(data.get("password") ?? "").trim() || null, role });
          e.currentTarget.reset();
        }}
      >
        <p className="text-sm font-medium">Add a login</p>
        {add.isError && <Alert variant="destructive"><AlertDescription>{add.error instanceof ApiError ? add.error.message : "Could not add the login."}</AlertDescription></Alert>}
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="add-email">Email</Label>
            <Input id="add-email" name="email" type="email" required />
          </div>
          <div className="space-y-1.5">
            <Label>Can</Label>
            <Select value={role} onValueChange={(v) => setRole(v as typeof role)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="tenant_admin">Manage</SelectItem>
                <SelectItem value="tenant_user">View only</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="add-password">Password (blank = generate)</Label>
            <Input id="add-password" name="password" type="password" />
          </div>
        </div>
        <Button type="submit" disabled={add.isPending}>
          {add.isPending && <Loader2 className="animate-spin" />} Add login
        </Button>
      </form>

      {query.data && query.data.length > 0 && (
        <div className="max-w-xl space-y-3">
          <p className="text-sm font-medium">Reset a password</p>
          <div className="flex gap-2">
            <Select value={resetWho} onValueChange={setResetWho}>
              <SelectTrigger className="flex-1"><SelectValue placeholder="Choose a login" /></SelectTrigger>
              <SelectContent>
                {query.data.map((u) => (
                  <SelectItem key={u.id} value={u.id}>{u.email}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" disabled={!resetWho || reset.isPending} onClick={() => reset.mutate(resetWho)}>
              {reset.isPending && <Loader2 className="animate-spin" />} Reset
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
