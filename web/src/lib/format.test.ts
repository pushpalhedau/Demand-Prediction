import { describe, expect, it } from "vitest";
import { formatMoney, formatMonth, formatNumber, formatPercent } from "./format";
import { translate, translateValue } from "./i18n";

const eur = { currency_symbol: "€", symbol_position: null } as const;
const aed = { currency_symbol: "AED", symbol_position: "prefix" } as const;
const usd = { currency_symbol: "$", symbol_position: null } as const;

describe("money", () => {
  it("puts the symbol where the language and tenant expect it", () => {
    expect(formatMoney(3_040_000_000, eur, "en")).toBe("€3.04B");
    expect(formatMoney(3_040_000_000, eur, "de")).toBe("3,04 Mrd. €");
    expect(formatMoney(742_000_000, aed, "en")).toBe("AED 742.0M");
    expect(formatMoney(940_000, usd, "en")).toBe("$940K");
    expect(formatMoney(1_234_567, eur, "de", false)).toBe("1.234.567 €");
  });
  it("treats a missing value as zero", () => {
    expect(formatMoney(null, usd, "en")).toBe("$0");
  });
});

describe("numbers", () => {
  it("uses the language's separators", () => {
    expect(formatNumber(1234567, "en")).toBe("1,234,567");
    expect(formatNumber(1234567, "de")).toBe("1.234.567");
    expect(formatPercent(12.4, "de")).toBe("12,4 %");
    expect(formatPercent(8.1, "en", 1, true)).toBe("+8.1%");
    expect(formatPercent(-3, "en", 1, true)).toBe("−3.0%");
  });
  it("shows n/a for a missing value", () => {
    expect(formatPercent(null, "en")).toBe("n/a");
    expect(formatNumber(undefined, "de")).toBe("–");
  });
});

describe("months", () => {
  it("does not shift with the timezone", () => {
    expect(formatMonth("2026-01-01", "en")).toBe("Jan 2026");
    expect(formatMonth("2026-03-01", "de")).toBe("Mär 2026");
  });
});

describe("translations", () => {
  it("fills placeholders and falls back to the key", () => {
    expect(translate("en", "val.units", { v: "5" })).toBe("5 units");
    expect(translate("en", "no.such.key")).toBe("no.such.key");
  });
  it("translates data values only for display", () => {
    expect(translateValue("de", "Compact")).toBe("Kompaktklasse");
    expect(translateValue("en", "Compact")).toBe("Compact");
  });
});
