// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { clearFlashStorage, peekFlash, setFlash } from "./flash";

describe("flash", () => {
  beforeEach(() => sessionStorage.clear());

  it("stores and peeks without consuming it", () => {
    expect(peekFlash()).toBeNull();
    setFlash({ title: "Created", email: "a@b.co", password: "secret" });
    expect(peekFlash()).toEqual({ title: "Created", email: "a@b.co", password: "secret" });
    expect(peekFlash()).not.toBeNull(); // peeking twice must not clear it
  });

  it("clears on an explicit clear, not on peek", () => {
    setFlash({ title: "Created", email: "a@b.co", password: "secret" });
    clearFlashStorage();
    expect(peekFlash()).toBeNull();
  });
});
