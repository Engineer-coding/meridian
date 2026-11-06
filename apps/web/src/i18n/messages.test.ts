import { describe, expect, it } from "vitest";

import { MESSAGES, pickLocale, translate } from "./messages";

describe("dil", () => {
  it("iki dilde de aynı anahtarlar dolu", () => {
    expect(Object.keys(MESSAGES.en).sort()).toEqual(Object.keys(MESSAGES.tr).sort());
    expect(Object.values(MESSAGES.en).every(Boolean)).toBe(true);
  });

  it("parametreleri yerleştirir", () => {
    expect(translate("tr", "sourcesTitle", { count: 3 })).toBe("3 kaynak");
  });

  it("tarayıcı dilini seçer, bilinmiyorsa Türkçe", () => {
    expect(pickLocale("en-US,en;q=0.9")).toBe("en");
    expect(pickLocale("tr-TR")).toBe("tr");
    expect(pickLocale("de")).toBe("tr");
    expect(pickLocale(null)).toBe("tr");
  });
});
