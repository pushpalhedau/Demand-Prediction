"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError, api } from "@/lib/api";
import { CURRENCY_SYMBOLS, LANGUAGES, REGION_LABELS } from "@/lib/constants";
import { setFlash } from "@/lib/flash";
import type { CreatedCredentials } from "@/lib/types";

export function CreateAccountDialog() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState<"en" | "de">("en");
  const [regionLabel, setRegionLabel] = useState<string>(REGION_LABELS[1]);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<CreatedCredentials>("/api/admin/accounts", { method: "POST", body }),
    onSuccess: async (created, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-accounts"] });
      const name = variables.name as string;
      setFlash({ title: `Account "${name}" created. Next: upload their data.`, email: created.email, password: created.password ?? "" });
      setOpen(false);
      router.push(`/accounts/${created.slug}`);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not create the account."),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const data = new FormData(event.currentTarget);
    const currency = String(data.get("currency") ?? "USD").toUpperCase();
    const symbol = String(data.get("symbol") ?? "").trim();
    create.mutate({
      name: String(data.get("name") ?? "").trim(),
      slug: String(data.get("slug") ?? "").trim(),
      admin_email: String(data.get("email") ?? "").trim(),
      admin_password: String(data.get("password") ?? "").trim() || null,
      config: {
        currency,
        currency_symbol: symbol || CURRENCY_SYMBOLS[currency] || currency,
        language,
        region_label: regionLabel,
        country_name: String(data.get("country") ?? "").trim(),
        news_gl: String(data.get("gl") ?? "").trim().toUpperCase(),
        news_hl: language,
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Create account
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create a new account</DialogTitle>
          <DialogDescription>Name, currency, language, what they call regions, country for local news, and their first admin&apos;s email.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="name">Account name</Label>
              <Input id="name" name="name" placeholder="Acme Motors Group" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="slug">Short id (optional)</Label>
              <Input id="slug" name="slug" placeholder="acme-motors" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="email">First admin&apos;s email</Label>
              <Input id="email" name="email" type="email" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password (blank = generate)</Label>
              <Input id="password" name="password" type="password" />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="currency">Currency</Label>
              <Input id="currency" name="currency" defaultValue="USD" maxLength={3} className="uppercase" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="symbol">Symbol</Label>
              <Input id="symbol" name="symbol" placeholder="auto" maxLength={4} />
            </div>
            <div className="space-y-1.5">
              <Label>Language</Label>
              <Select value={language} onValueChange={(v) => setLanguage(v as "en" | "de")}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(LANGUAGES).map(([code, name]) => (
                    <SelectItem key={code} value={code}>{name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Regions called</Label>
              <Select value={regionLabel} onValueChange={setRegionLabel}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {REGION_LABELS.map((r) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="country">Country (for local news)</Label>
              <Input id="country" name="country" placeholder="United Kingdom" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gl">Country code (2 letters)</Label>
              <Input id="gl" name="gl" placeholder="GB" maxLength={2} className="uppercase" />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="animate-spin" />} Create account
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
