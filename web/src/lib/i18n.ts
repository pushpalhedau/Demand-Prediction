import de from "@/i18n/de.json";
import en from "@/i18n/en.json";
import values from "@/i18n/values.json";
import type { Lang } from "./types";

const dictionaries: Record<Lang, Record<string, string>> = { en, de };
const valueMap = values as Record<string, string>;

export const LANGUAGES: Record<Lang, string> = { en: "English", de: "Deutsch" };

export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "de";
}

/** Look up a UI string and fill `{name}` placeholders. Falls back to English, then to the key itself. */
export function translate(lang: Lang, key: string, vars: Record<string, string | number> = {}): string {
  const template = dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => (name in vars ? String(vars[name]) : whole));
}

/** Translate a data value (segment, fuel type…) for display only; filters and queries keep the canonical value. */
export function translateValue(lang: Lang, value: string): string {
  return lang === "de" ? (valueMap[value] ?? value) : value;
}
