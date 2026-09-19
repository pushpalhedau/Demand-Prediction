import type { Lang, Organisation } from "./types";

/** Locale-aware presentation, mirroring the rules the Streamlit app used (en/de separators, tenant currency). */

const DE_MONTHS_SHORT = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const EN_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const locale = (lang: Lang) => (lang === "de" ? "de-DE" : "en-US");

export function formatNumber(value: number | null | undefined, lang: Lang, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return lang === "de" ? "–" : "n/a";
  return new Intl.NumberFormat(locale(lang), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

export function formatPercent(value: number | null | undefined, lang: Lang, digits = 1, signed = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return lang === "de" ? "–" : "n/a";
  const body = formatNumber(Math.abs(value), lang, digits);
  const unit = lang === "de" ? " %" : "%";
  if (signed && value > 0) return `+${body}${unit}`;
  if (signed && value < 0) return `−${body}${unit}`;
  return `${body}${unit}`;
}

function symbolAfter(org: Pick<Organisation, "symbol_position">, lang: Lang): boolean {
  return org.symbol_position ? org.symbol_position === "suffix" : lang === "de";
}

function withSymbol(text: string, org: Pick<Organisation, "currency_symbol" | "symbol_position">, lang: Lang): string {
  const sym = org.currency_symbol;
  if (symbolAfter(org, lang)) return `${text} ${sym}`;
  return /^[A-Za-z]+$/.test(sym) ? `${sym} ${text}` : `${sym}${text}`;
}

type MoneyOrg = Pick<Organisation, "currency_symbol" | "symbol_position">;

/** €3.04B / AED 742.0M / $940K in English; 3,04 Mrd. € / 742,0 Mio. € / 940 Tsd. € in German. */
export function formatMoney(value: number | null | undefined, org: MoneyOrg, lang: Lang, compact = true): string {
  const v = value ?? 0;
  const a = Math.abs(v);
  if (compact) {
    const scales: [number, number, string, string][] = [
      [1e9, 2, "B", " Mrd."],
      [1e6, 1, "M", " Mio."],
      [1e3, 0, "K", " Tsd."],
    ];
    for (const [limit, digits, en, de] of scales) {
      if (a >= limit) {
        return withSymbol(`${formatNumber(v / limit, lang, digits)}${lang === "de" ? de : en}`, org, lang);
      }
    }
  }
  return withSymbol(formatNumber(v, lang, 0), org, lang);
}

/** "Jan 2026" for a date string like 2026-01-01 (read as UTC, so the month never shifts with the viewer's timezone). */
export function formatMonth(iso: string, lang: Lang): string {
  const [year, month] = iso.split("-");
  const names = lang === "de" ? DE_MONTHS_SHORT : EN_MONTHS_SHORT;
  return `${names[Number(month) - 1] ?? month} ${year}`;
}

/** Compact count for axes and labels. EN: 9.4K / 1.2M / 320.  DE: 9,4 Tsd. / 1,2 Mio. / 320. */
export function formatCompact(value: number | null | undefined, lang: Lang): string {
  const n = value ?? 0;
  const a = Math.abs(n);
  if (lang === "de") {
    if (a >= 1e6) return `${formatNumber(n / 1e6, lang, 1)} Mio.`;
    if (a >= 1e4) return `${formatNumber(n / 1e3, lang, 0)} Tsd.`;
    if (a >= 1e3) return `${formatNumber(n / 1e3, lang, 1)} Tsd.`;
    return formatNumber(n, lang, 0);
  }
  if (a >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (a >= 1e4) return `${(n / 1e3).toFixed(0)}K`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return formatNumber(n, lang, 0);
}

/** Month name for 1–12 in the UI language ("Jan" / "Mär"). */
export function monthName(month: number, lang: Lang): string {
  return (lang === "de" ? DE_MONTHS_SHORT : EN_MONTHS_SHORT)[month - 1] ?? String(month);
}

const DE_DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const EN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
/** Weekday for 0 (Monday) – 6 (Sunday). */
export function dayName(day: number, lang: Lang): string {
  return (lang === "de" ? DE_DAYS : EN_DAYS)[day] ?? String(day);
}

/** "31 Aug 2026" / "31.08.2026" for an ISO date, read as UTC so it never shifts with the viewer's timezone. */
export function formatDate(iso: string, lang: Lang): string {
  const date = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale(lang), { day: lang === "de" ? "2-digit" : "numeric", month: lang === "de" ? "2-digit" : "short", year: "numeric", timeZone: "UTC" }).format(date);
}
