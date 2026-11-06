const POLL_MS = 3000;
const ACTIVE = new Set(["pending", "indexing", "deleting"]);

/** Bir kaynak işlemdeyken liste canlı izlenir; hepsi durunca istek atılmaz. */
export function refetchWhileActive(items: { status: string }[]): number | false {
  return items.some((item) => ACTIVE.has(item.status)) ? POLL_MS : false;
}
