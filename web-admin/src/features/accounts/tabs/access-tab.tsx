"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { AccountDetail } from "@/lib/types";

export function AccessTab({ account }: { account: AccountDetail }) {
  const queryClient = useQueryClient();
  const [sure, setSure] = useState(false);

  const setStatus = useMutation({
    mutationFn: (status: "active" | "suspended") => api(`/api/admin/accounts/${account.slug}/status`, { method: "POST", body: { status } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-account", account.slug] }),
  });

  if (account.status !== "active") {
    return (
      <div className="max-w-xl space-y-4">
        <Alert variant="destructive">
          <AlertTitle>This account is suspended.</AlertTitle>
          <AlertDescription>Its users cannot sign in.</AlertDescription>
        </Alert>
        <Button onClick={() => setStatus.mutate("active")} disabled={setStatus.isPending}>
          {setStatus.isPending && <Loader2 className="animate-spin" />} Reactivate account
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-4">
      <p className="text-muted-foreground text-sm leading-relaxed">
        Suspending blocks every login for this account. Their data is kept. People already signed in are locked out within a few minutes.
      </p>
      <div className="flex items-center gap-2">
        <Checkbox id="sure" checked={sure} onCheckedChange={(v) => setSure(v === true)} />
        <Label htmlFor="sure" className="text-sm font-normal">I want to suspend this account</Label>
      </div>
      <Button variant="destructive" disabled={!sure || setStatus.isPending} onClick={() => setStatus.mutate("suspended")}>
        {setStatus.isPending && <Loader2 className="animate-spin" />} Suspend account
      </Button>
    </div>
  );
}
