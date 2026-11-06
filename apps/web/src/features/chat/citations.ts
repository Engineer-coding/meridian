import type { PhrasingContent, Root, Text } from "mdast";

type Parent = { type: string; children?: Node[] };
type Node = Parent | Text;

const CITATION = /\[(\d{1,2})\]/g;

function split(node: Text): PhrasingContent[] {
  const parts: PhrasingContent[] = [];
  let last = 0;
  for (const match of node.value.matchAll(CITATION)) {
    if (match.index > last) parts.push({ type: "text", value: node.value.slice(last, match.index) });
    parts.push({
      type: "text",
      value: match[0],
      data: { hName: "cite", hProperties: { n: match[1] }, hChildren: [] },
    } as unknown as PhrasingContent);
    last = match.index + match[0].length;
  }
  if (last < node.value.length) parts.push({ type: "text", value: node.value.slice(last) });
  return parts;
}

function walk(node: Parent): void {
  if (!node.children) return;
  // Kod içindeki `arr[1]` atıf değildir: code ve inlineCode düğümleri `text` olmadığı için dokunulmaz.
  node.children = node.children.flatMap((child) =>
    child.type === "text" ? (split(child as Text) as unknown as Node[]) : (walk(child as Parent), [child]),
  );
}

/** Metindeki `[n]` işaretlerini <cite n="n"> düğümüne çevirir; ham HTML'e hiç dokunulmaz. */
export function remarkCitations() {
  return (tree: Root) => walk(tree as unknown as Parent);
}

/** Kaynak önizlemesi düz metin gösterilir: Markdown işaretleri okunmayı zorlaştırır. */
export function plainExcerpt(text: string, limit?: number): string {
  const plain = text
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/`+([^`]*)`+/g, "$1")
    .replace(/(^|[\s(])[_*]{1,2}([^_*\n]+)[_*]{1,2}(?=$|[\s).,;:])/g, "$1$2");
  return limit && plain.length > limit ? `${plain.slice(0, limit).trimEnd()}…` : plain;
}

/** Yalnızca http(s) bağlantı: belge verisinden gelen `javascript:` adresi açılamaz. */
export function safeHttpUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const { protocol } = new URL(url);
    return protocol === "http:" || protocol === "https:" ? url : undefined;
  } catch {
    return undefined;
  }
}
