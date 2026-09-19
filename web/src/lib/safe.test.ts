import { describe, expect, it } from "vitest";
import { safeUrl } from "./safe";

describe("safeUrl", () => {
  it("allows plain web links", () => {
    expect(safeUrl("https://example.com/a?b=1")).toBe("https://example.com/a?b=1");
    expect(safeUrl("http://example.com")).toBe("http://example.com/");
  });
  it("rejects anything that could run script or is not a link", () => {
    for (const bad of ["javascript:alert(1)", "data:text/html,<script>", "vbscript:x", "//evil.example", "not a url", "", null, undefined]) {
      expect(safeUrl(bad as string | null | undefined)).toBeNull();
    }
  });
});
