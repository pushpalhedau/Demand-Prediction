"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/admin/lib/api";

/** Irreversible: the operator must retype the account's short id, and the API checks it again. */
export function DeleteAccount({ slug, name }: { slug: string; name: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [typed, setTyped] = useState("");

  const remove = useMutation({
    mutationFn: () => api(`/api/admin/accounts/${slug}/delete`, { method: "POST", body: { confirm: typed } }),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ["admin-account", slug] });
      await queryClient.invalidateQueries({ queryKey: ["admin-accounts"] });
      toast.success(`"${name}" was deleted.`);
      router.push("/admin");
    },
  });

  return (
    <div className="max-w-xl space-y-3 border-t pt-6">
      <h3 className="text-destructive text-sm font-semibold">Delete this account</h3>
      <p className="text-muted-foreground text-sm leading-relaxed">
        Permanently removes the account, all its logins, every imported row, uploaded files and trained models. This cannot be undone. The audit log keeps a record.
      </p>
      {remove.isError && (
        <Alert variant="destructive">
          <AlertDescription>{remove.error instanceof ApiError ? remove.error.message : "Could not delete the account."}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="confirm-delete">
          Type <span className="font-mono">{slug}</span> to confirm
        </Label>
        <Input id="confirm-delete" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </div>
      <Button variant="destructive" disabled={typed !== slug || remove.isPending} onClick={() => remove.mutate()}>
        {remove.isPending && <Loader2 className="animate-spin" />} Delete account permanently
      </Button>
    </div>
  );
}
