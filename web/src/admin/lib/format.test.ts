import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatNumber } from "./format";

describe("formatNumber", () => {
  it("uses US separators and shows a dash for a missing value", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(1234.5, 1)).toBe("1,234.5");
    expect(formatNumber(null)).toBe("–");
    expect(formatNumber(undefined)).toBe("–");
  });
});

describe("formatDate", () => {
  it("does not shift with the viewer's timezone", () => {
    expect(formatDate("2026-01-31")).toBe("Jan 31, 2026");
  });
  it("shows a dash for a missing value", () => {
    expect(formatDate(null)).toBe("–");
    expect(formatDate(undefined)).toBe("–");
  });
});

describe("formatDateTime", () => {
  it("shows a dash for a missing value and formats a real timestamp", () => {
    expect(formatDateTime(null)).toBe("–");
    expect(formatDateTime("2026-09-20T05:30:00Z")).toContain("2026");
  });
});
