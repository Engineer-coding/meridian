import { describe, expect, it } from "vitest";

import { formatMetric, thresholdState } from "./evalMath";
import { refetchWhileActive } from "./sourceStatus";
import { niceMax, quotaState } from "./usageMath";

describe("kota göstergesi", () => {
  it("seviyeyi eşiklerden, genişliği %100 ile sınırlı hesaplar", () => {
    expect(quotaState(0, 1000)).toEqual({ percent: 0, level: "ok" });
    expect(quotaState(799, 1000)).toEqual({ percent: 80, level: "ok" });
    expect(quotaState(800, 1000)).toEqual({ percent: 80, level: "high" });
    expect(quotaState(1000, 1000)).toEqual({ percent: 100, level: "full" });
    expect(quotaState(1500, 1000)).toEqual({ percent: 100, level: "full" });
  });
});

describe("grafik ekseni", () => {
  it("en büyük değerin üstünde yuvarlak bir sınır seçer", () => {
    expect(niceMax(0)).toBe(1);
    expect(niceMax(1)).toBe(1);
    expect(niceMax(1650)).toBe(2000);
    expect(niceMax(4200)).toBe(5000);
    expect(niceMax(5001)).toBe(10000);
  });
});

describe("kaynak listesi izleme", () => {
  it("yalnızca işlemde kaynak varken yeniler", () => {
    expect(refetchWhileActive([{ status: "ready" }, { status: "failed" }])).toBe(false);
    expect(refetchWhileActive([{ status: "ready" }, { status: "indexing" }])).toBe(3000);
    expect(refetchWhileActive([])).toBe(false);
  });
});

describe("değerlendirme tablosu", () => {
  it("eşiği iki yönde denetler", () => {
    expect(thresholdState(0.61, 0.57)).toBe("ok");
    expect(thresholdState(0.5, 0.57)).toBe("fail");
    expect(thresholdState(0.4, undefined, 0.35)).toBe("fail");
    expect(thresholdState(0.3, undefined, 0.35)).toBe("ok");
    expect(thresholdState(undefined, 0.5)).toBe("none");
    expect(thresholdState(0.5)).toBe("none");
  });

  it("birimi metrikten seçer, ölçülmemişi boş gösterir", () => {
    expect(formatMetric("correct", 0.61, "en")).toBe("61%");
    expect(formatMetric("mrr", 0.8157, "en")).toBe("0.816");
    expect(formatMetric("median_total_seconds", 64.9, "en")).toBe("64.9 sn");
    expect(formatMetric("correct", undefined, "en")).toBe("–");
  });
});
