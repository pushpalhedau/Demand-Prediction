"use client";

import { BarChart3, Boxes, Newspaper, Scale } from "lucide-react";
import Image from "next/image";
import { useEffect, useState } from "react";

const INSIGHTS = [
  {
    icon: BarChart3,
    title: "Forecast before the market moves",
    body: "Brand, segment and store-level demand projections with confidence bands, not single-point guesses.",
  },
  {
    icon: Scale,
    title: "Separate what you control",
    body: "Year-over-year change is split into your own execution and the market forces handed to you.",
  },
  {
    icon: Boxes,
    title: "Stock the right cars in the right rooftop",
    body: "Inventory, ageing and customer signals sit next to demand so transfers and orders are informed.",
  },
  {
    icon: Newspaper,
    title: "Read the market signal",
    body: "News and sentiment are distilled into a demand advisory across every module.",
  },
];

const HISTORY = "M0,150 C40,140 60,120 100,124 S160,96 200,92 S260,70 300,62";
const FORECAST = "M300,62 C340,52 370,34 410,30 S470,22 500,14";
const BAND = "M300,62 C340,50 370,26 410,16 S470,0 500,-10 L500,40 C470,46 440,52 410,50 S340,74 300,62 Z";

// Echoes the crossed-ellipse X in the logo mark.
export function Orbit({ className, reverse }: { className: string; reverse?: boolean }) {
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden>
      <defs>
        <linearGradient id="lg-x" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1e90ff" />
          <stop offset="1" stopColor="#6be05a" />
        </linearGradient>
      </defs>
      <g className="lg-anim" style={{ animation: `lg-spin 60s linear infinite${reverse ? " reverse" : ""}`, transformOrigin: "100px 100px" }}>
        <ellipse cx="100" cy="100" rx="90" ry="26" transform="rotate(45 100 100)" fill="none" stroke="url(#lg-x)" strokeWidth="6" />
        <ellipse cx="100" cy="100" rx="90" ry="26" transform="rotate(-45 100 100)" fill="none" stroke="url(#lg-x)" strokeWidth="6" />
      </g>
    </svg>
  );
}

function ForecastChart() {
  return (
    <div className="lg-rise rounded-2xl border border-white/10 bg-white/[0.06] p-5 backdrop-blur-sm" style={{ animationDelay: "0.5s" }}>
      <div className="mb-3 flex items-center justify-between text-xs">
        <span className="font-medium text-white/90">Monthly unit demand</span>
        <span className="flex items-center gap-3 text-white/60">
          <span className="flex items-center gap-1.5"><i className="h-0.5 w-4 rounded bg-[#38bdf8]" />Actual</span>
          <span className="flex items-center gap-1.5"><i className="w-4 border-t-2 border-dashed border-[#4ade80]" />Forecast</span>
        </span>
      </div>
      <svg viewBox="0 0 500 170" className="w-full overflow-visible" role="img" aria-label="Illustrative demand forecast with confidence band">
        <defs>
          <linearGradient id="lg-hist" x1="0" x2="1"><stop offset="0" stopColor="#38bdf8" /><stop offset="1" stopColor="#22d3ee" /></linearGradient>
          <linearGradient id="lg-band" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#4ade80" stopOpacity="0.35" /><stop offset="1" stopColor="#4ade80" stopOpacity="0.04" /></linearGradient>
        </defs>
        {[30, 70, 110, 150].map((y) => (
          <line key={y} x1="0" x2="500" y1={y} y2={y} stroke="white" strokeOpacity="0.07" />
        ))}
        <line x1="300" x2="300" y1="0" y2="170" stroke="white" strokeOpacity="0.2" strokeDasharray="3 4" />
        <path d={BAND} fill="url(#lg-band)" className="lg-fade" style={{ animationDelay: "2.4s" }} />
        <path d={HISTORY} pathLength={1} fill="none" stroke="url(#lg-hist)" strokeWidth="3" strokeLinecap="round" className="lg-draw" style={{ animationDelay: "0.9s" }} />
        <path d={FORECAST} fill="none" stroke="#4ade80" strokeWidth="3" strokeLinecap="round" strokeDasharray="8 7" className="lg-fade" style={{ animationDelay: "2.6s" }} />
        <g className="lg-fade" style={{ animationDelay: "3.1s" }}>
          <circle cx="300" cy="62" r="4" fill="#fff" className="lg-anim" style={{ transformOrigin: "300px 62px", animation: "lg-ping 2s ease-out infinite" }} />
          <circle cx="300" cy="62" r="4.5" fill="#fff" />
          <text x="306" y="166" fontSize="10" fill="white" fillOpacity="0.55">Today</text>
        </g>
      </svg>
      <p className="mt-2 text-[10px] tracking-wide text-white/40 uppercase">Illustrative</p>
    </div>
  );
}

function InsightRotator() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setI((n) => (n + 1) % INSIGHTS.length), 5000);
    return () => clearTimeout(t);
  }, [i]);
  const { icon: Icon, title, body } = INSIGHTS[i]!;
  return (
    <div className="lg-rise" style={{ animationDelay: "0.8s" }}>
      <div key={i} className="lg-anim flex min-h-[5.5rem] gap-4" style={{ animation: "lg-swap 5s ease both" }}>
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400/30 to-emerald-400/30 ring-1 ring-white/15">
          <Icon className="size-5 text-white" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-white/70">{body}</p>
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        {INSIGHTS.map((s, n) => (
          <button
            key={s.title}
            type="button"
            aria-label={s.title}
            aria-current={n === i}
            onClick={() => setI(n)}
            className="h-1 flex-1 overflow-hidden rounded-full bg-white/15"
          >
            {n === i && <span className="lg-anim block h-full origin-left bg-gradient-to-r from-sky-400 to-emerald-400" style={{ animation: "lg-bar 5s linear both" }} />}
            {n < i && <span className="block h-full bg-white/50" />}
          </button>
        ))}
      </div>
    </div>
  );
}

export function LoginHero() {
  return (
    <section className="relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex">
      <div className="lg-rise relative self-start">
        <div aria-hidden className="absolute -inset-x-10 -inset-y-6 rounded-full bg-sky-400/20 blur-2xl" />
        <Image
          src="/logo.png"
          alt="PredictaX — AI demand forecasting"
          width={230}
          height={58}
          priority
          className="relative drop-shadow-[0_2px_18px_rgba(56,189,248,0.35)]"
        />
      </div>

      <div className="relative max-w-xl space-y-8">
        <div className="lg-rise space-y-3" style={{ animationDelay: "0.2s" }}>
          <h2 className="text-4xl leading-[1.1] font-semibold tracking-tight">
            Demand intelligence for{" "}
            <span className="bg-gradient-to-r from-sky-300 to-emerald-300 bg-clip-text text-transparent">automotive retail groups.</span>
          </h2>
          <p className="max-w-md text-sm text-white/65">One place to see what will sell, where, and why across every rooftop you run.</p>
        </div>
        <ForecastChart />
        <InsightRotator />
      </div>

      <p className="lg-fade relative text-xs text-white/50" style={{ animationDelay: "1.2s" }}>
        © {new Date().getFullYear()} PredictaX · Secure, tenant-isolated access
      </p>
    </section>
  );
}
