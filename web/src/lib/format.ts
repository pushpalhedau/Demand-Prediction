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
