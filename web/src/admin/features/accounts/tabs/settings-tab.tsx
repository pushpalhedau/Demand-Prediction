"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError, api } from "@/admin/lib/api";
import { LANGUAGES, REGION_LABELS } from "@/admin/lib/constants";
import type { AccountConfig } from "@/admin/lib/types";

export function SettingsTab({ slug, config }: { slug: string; config: AccountConfig }) {
  const queryClient = useQueryClient();
  const [language, setLanguage] = useState<"en" | "de">(config.language ?? "en");
  const [position, setPosition] = useState<"prefix" | "suffix">(config.symbol_position ?? "prefix");
  const [regionLabel, setRegionLabel] = useState(config.region_label ?? REGION_LABELS[0]);

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api(`/api/admin/accounts/${slug}/settings`, { method: "PATCH", body }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-account", slug] });
      toast.success("Saved. The customer sees it on their next page load.");
    },
  });

  return (
    <form
      className="max-w-2xl space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        save.mutate({
          currency: String(data.get("currency") ?? "").toUpperCase(),
          currency_symbol: String(data.get("symbol") ?? ""),
          symbol_position: position,
          language,
          region_label: regionLabel,
          country_name: String(data.get("country") ?? ""),
          news_gl: String(data.get("gl") ?? "").toUpperCase(),
          news_hl: language,
        });
      }}
    >
      {save.isError && (
        <Alert variant="destructive">
          <AlertDescription>{save.error instanceof ApiError ? save.error.message : "Could not save the settings."}</AlertDescription>
        </Alert>
      )}
      <div className="grid grid-cols-4 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="currency">Currency code</Label>
          <Input id="currency" name="currency" defaultValue={config.currency ?? "USD"} maxLength={3} className="uppercase" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="symbol">Symbol</Label>
          <Input id="symbol" name="symbol" defaultValue={config.currency_symbol ?? ""} maxLength={4} />
        </div>
        <div className="space-y-1.5">
          <Label>Symbol goes</Label>
          <Select value={position} onValueChange={(v) => setPosition(v as typeof position)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="prefix">Before</SelectItem>
              <SelectItem value="suffix">After</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Language</Label>
          <Select value={language} onValueChange={(v) => setLanguage(v as typeof language)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {Object.entries(LANGUAGES).map(([code, name]) => (
                <SelectItem key={code} value={code}>{name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label>Regions are called</Label>
          <Select value={regionLabel} onValueChange={setRegionLabel}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {REGION_LABELS.map((r) => (
                <SelectItem key={r} value={r}>{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="country">Country (for local news)</Label>
          <Input id="country" name="country" defaultValue={config.country_name ?? ""} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="gl">Country code (2 letters)</Label>
          <Input id="gl" name="gl" defaultValue={config.news_gl ?? ""} maxLength={2} className="uppercase" />
        </div>
      </div>
      <Button type="submit" disabled={save.isPending}>
        {save.isPending && <Loader2 className="animate-spin" />} Save settings
      </Button>
    </form>
  );
}
