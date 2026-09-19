import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import extraDe from "./extra.de.json";
import extraEn from "./extra.en.json";
import en from "./en.json";
import de from "./de.json";

const SRC = join(__dirname, "..");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

/** Literal keys passed to t("…") anywhere in the app, plus the t(`prefix.${x}`) families it builds. */
function usedKeys(): { literal: Map<string, string>; prefixes: Set<string> } {
  const literal = new Map<string, string>();
  const prefixes = new Set<string>();
  for (const file of sources(SRC)) {
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(/\bt\(\s*"([a-z]{1,4}\.[A-Za-z0-9_.]+)"/g)) literal.set(m[1]!, file);
    for (const m of text.matchAll(/\bt\(\s*`([a-z]{1,4}\.[A-Za-z0-9_.]*)\$\{/g)) prefixes.add(m[1]!);
    for (const m of text.matchAll(/(?:tab|key)\s*[:=]\s*"(tab\.[a-z]+)"/g)) literal.set(m[1]!, file);
  }
  return { literal, prefixes };
}

const english: Record<string, string> = { ...en, ...extraEn };
const german: Record<string, string> = { ...de, ...extraDe };

describe("translations", () => {
  const { literal, prefixes } = usedKeys();

  it("defines every key the code uses", () => {
    const missing = [...literal].filter(([key]) => !(key in english)).map(([key, file]) => `${key}  (${file.replace(SRC, "src")})`);
    expect(missing).toEqual([]);
  });

  it("has at least one entry behind every dynamic key family", () => {
    const empty = [...prefixes].filter((p) => !Object.keys(english).some((k) => k.startsWith(p)));
    expect(empty).toEqual([]);
  });

  it("gives every dashboard-specific string a German version", () => {
    const untranslated = Object.keys(extraEn).filter((k) => !(k in extraDe));
    expect(untranslated).toEqual([]);
    expect(Object.keys(extraDe).filter((k) => !(k in extraEn))).toEqual([]);
  });

  it("keeps placeholders identical between languages", () => {
    const names = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
    const drift = Object.keys(extraEn).filter((k) => names(extraEn[k as keyof typeof extraEn]!) !== names(german[k]!));
    expect(drift).toEqual([]);
  });
});
