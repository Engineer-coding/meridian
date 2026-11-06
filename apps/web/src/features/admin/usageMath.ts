/** Eksen üst sınırı: en büyük değerin üstündeki yuvarlak sayı (1, 2 ya da 5 × 10^n). */
export function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const factor = [1, 2, 5, 10].find((candidate) => candidate * magnitude >= value)!;
  return factor * magnitude;
}

export type QuotaLevel = "ok" | "high" | "full";

/** Çubuk genişliği %100'ü aşmaz. Kota yumuşak olduğu için kullanım sınırı geçebilir. */
export function quotaState(used: number, limit: number): { percent: number; level: QuotaLevel } {
  const ratio = limit > 0 ? used / limit : 1;
  const percent = Math.min(100, Math.round(ratio * 100));
  return { percent, level: ratio >= 1 ? "full" : ratio >= 0.8 ? "high" : "ok" };
}
