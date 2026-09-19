"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2 } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";

const HIGHLIGHTS = [
  "Demand forecasts by brand, segment and store",
  "Year-over-year performance split into what you control and what you don't",
  "Inventory, customer and market signals in one place",
];

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: { email: String(data.get("email") ?? ""), password: String(data.get("password") ?? "") },
      });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.replace("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the server. Please try again.");
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden bg-[oklch(0.3_0.09_258)] text-white flex-col justify-between p-12 lg:flex">
        <div className="rounded-md bg-white/95 px-4 py-2.5 self-start">
          <Image src="/logo.png" alt="PredictaX" width={150} height={38} priority />
        </div>
        <div className="max-w-md space-y-6">
          <h2 className="text-3xl leading-tight font-semibold tracking-tight">Demand intelligence for automotive retail groups.</h2>
          <ul className="space-y-3 text-sm text-white/85">
            {HIGHLIGHTS.map((line) => (
              <li key={line} className="flex gap-3">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-current" aria-hidden />
                {line}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-white/60 text-xs">© {new Date().getFullYear()} PredictaX</p>
      </section>

      <section className="flex items-center justify-center p-6">
        <Card className="w-full max-w-sm border-0 shadow-none sm:border sm:shadow-sm">
          <CardHeader className="space-y-1">
            <div className="mb-2 lg:hidden">
              <Image src="/logo.png" alt="PredictaX" width={130} height={33} priority />
            </div>
            <CardTitle className="text-xl">Sign in</CardTitle>
            <CardDescription>Use the credentials provided for your organisation.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4" noValidate>
              {error && (
                <Alert variant="destructive">
                  <AlertCircle />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" name="email" type="email" autoComplete="username" required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" name="password" type="password" autoComplete="current-password" required />
              </div>
              <Button type="submit" className="w-full" disabled={busy}>
                {busy && <Loader2 className="animate-spin" />}
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
