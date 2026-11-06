export function formatMetric(metric: string, value: number | undefined, locale: string): string {
  if (value === undefined) return "–";
  if (metric === "median_total_seconds") {
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value)} sn`;
  }
  if (metric === "mrr") return new Intl.NumberFormat(locale, { minimumFractionDigits: 3 }).format(value);
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 }).format(value);
}

export function thresholdState(value: number | undefined, min?: number, max?: number): "ok" | "fail" | "none" {
  if (value === undefined || (min === undefined && max === undefined)) return "none";
  return (min !== undefined && value < min) || (max !== undefined && value > max) ? "fail" : "ok";
}
