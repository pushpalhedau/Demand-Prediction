"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail, ShieldCheck } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { LoginHero, Orbit } from "@/components/login/login-hero";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";

// Inputs are restyled for the dark surface; the shared Input keeps its behaviour.
const FIELD =
  "h-11 border-white/15 bg-white/[0.06] text-white placeholder:text-white/35 focus-visible:border-sky-400/70 focus-visible:ring-sky-400/25 dark:bg-white/[0.06]";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);

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
    <main className="relative grid min-h-screen overflow-hidden bg-[oklch(0.19_0.05_255)] text-white lg:grid-cols-[1.25fr_1fr]">
      {/* Shared backdrop so the hero and the form read as one surface. */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="lg-anim absolute top-1/4 -left-32 size-[30rem] rounded-full bg-sky-500/25 blur-3xl" style={{ animation: "lg-drift 18s ease-in-out infinite" }} />
        <div className="lg-anim absolute -right-20 -bottom-40 size-[32rem] rounded-full bg-emerald-400/20 blur-3xl" style={{ animation: "lg-drift 22s ease-in-out infinite reverse" }} />
        <div className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(white_1px,transparent_1px),linear-gradient(90deg,white_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_85%)]" />
      </div>

      <Orbit className="pointer-events-none absolute top-10 left-[55.5%] hidden size-[26rem] -translate-x-1/2 opacity-[0.14] lg:block" />

      <LoginHero />

      <section className="relative flex items-center justify-center overflow-hidden p-6 sm:p-10">
        <div className="lg-rise relative w-full max-w-md" style={{ animationDelay: "0.15s" }}>
          <div className="relative rounded-3xl border border-white/10 bg-white/[0.04] p-8 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-10">
            <div className="mb-8 lg:hidden">
              <Image src="/logo.png" alt="PredictaX" width={170} height={43} priority />
            </div>
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.06] px-2.5 py-1 text-[11px] font-medium text-white/70">
                <ShieldCheck className="size-3.5" /> Secure workspace
              </span>
              <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
              <p className="text-sm text-white/60">Sign in with the credentials provided for your organisation.</p>
            </div>

            <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
              {error && (
                <Alert variant="destructive" className="border-red-400/30 bg-red-500/10">
                  <AlertCircle />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-white/80">Email</Label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-white/45" />
                  <Input id="email" name="email" type="email" autoComplete="username" required className={`${FIELD} pl-10`} placeholder="you@company.com" />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-white/80">Password</Label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-white/45" />
                  <Input id="password" name="password" type={show ? "text" : "password"} autoComplete="current-password" required className={`${FIELD} px-10`} />
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    aria-label={show ? "Hide password" : "Show password"}
                    className="absolute top-1/2 right-2.5 -translate-y-1/2 rounded p-1 text-white/50 hover:text-white"
                  >
                    {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                disabled={busy}
                className="group flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-sky-500 text-sm font-semibold text-white transition hover:bg-sky-400 focus-visible:ring-3 focus-visible:ring-sky-400/40 focus-visible:outline-none disabled:opacity-60"
              >
                {busy ? <Loader2 className="size-4 animate-spin" /> : null}
                {busy ? "Signing in…" : "Sign in"}
                {!busy && <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />}
              </button>
            </form>

            <p className="mt-7 text-center text-xs text-white/45">
              Trouble signing in? Contact your organisation&apos;s administrator.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
