import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

import type { CitedSource } from "@/lib/api/client";

import { Answer, tooltipPosition } from "./Answer";
import { plainExcerpt, safeHttpUrl } from "./citations";

const source: CitedSource = {
  number: 1,
  documentPath: "kvkk/6698.md",
  title: "KVKK",
  section: "Madde 13",
  content: "Veri sorumlusu başvuruyu en geç otuz gün içinde sonuçlandırır.",
};

function show(text: string, onOpen = vi.fn()) {
  return { onOpen, ...render(<Answer text={text} sources={[source]} onOpenSource={onOpen} />) };
}

describe("cevap gösterimi", () => {
  it("[n] işaretini kaynağa bağlı düğmeye çevirir; tıklanınca kaynağı açar", async () => {
    const { onOpen } = show("Otuz gün içinde [1].");

    await userEvent.click(screen.getByRole("button", { name: "Kaynak 1: KVKK" }));

    expect(onOpen).toHaveBeenCalledWith(1);
  });

  it("üzerine gelince ve odaklanınca kaynak pasajını gösterir", async () => {
    show("Otuz gün [1].");
    const button = screen.getByRole("button");

    await userEvent.hover(button);
    expect(screen.getByRole("tooltip")).toHaveTextContent("otuz gün içinde");
    await userEvent.unhover(button);
    expect(screen.queryByRole("tooltip")).toBeNull();

    await userEvent.tab();
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("akış sürerken atıf düğmesi yeniden kurulmaz; odak kaybolmaz", async () => {
    const onOpen = vi.fn();
    const { rerender } = render(<Answer text="Otuz [1]" sources={[source]} onOpenSource={onOpen} />);
    const button = screen.getByRole("button");
    await userEvent.tab();
    expect(button).toHaveFocus();

    rerender(<Answer text="Otuz [1] gün" sources={[source]} onOpenSource={onOpen} />);

    expect(screen.getByRole("button")).toBe(button);
    expect(button).toHaveFocus();
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("var olmayan kaynak numarası bağlantı olmaz", () => {
    show("Uydurma [7].");

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("7")).toHaveClass("cite-invalid");
  });

  it("kod içindeki köşeli parantez atıf sayılmaz", () => {
    show("Bakın: `arr[1]`");
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("arr[1]")).toBeInTheDocument();
  });

  it("modelin yazdığı HTML ve tehlikeli bağlantılar çalışmaz", () => {
    const { container } = show(
      '<img src=x onerror="alert(1)"><script>alert(2)</script> ![dış](https://evil.test/p.png?q=gizli) [tıkla](javascript:alert(3)) [iyi](https://example.com)',
    );

    expect(container.querySelector("img, script")).toBeNull();
    // Ham HTML düz metin olarak görünür: etiket değildir, çalışmaz.
    expect(container.textContent).toContain("<img");
    expect(screen.queryByRole("link", { name: "tıkla" })).toBeNull();
    const good = screen.getByRole("link", { name: "iyi" });
    expect(good).toHaveAttribute("rel", "noopener noreferrer nofollow");
  });

  it("erişilebilirlik ihlali yok", async () => {
    const { container } = show("Otuz gün [1], uydurma [7].");
    const result = await axe.run(container);
    expect(result.violations).toEqual([]);
  });

  it("kaynak penceresi üstte yer yoksa altta açılır, ekran dışına taşmaz", () => {
    const chip = { left: 1200, width: 20, top: 100, bottom: 120 };

    expect(tooltipPosition(chip, 1280)).toMatchObject({ left: 932, width: 340, top: 126 });
    expect(tooltipPosition({ ...chip, top: 400, bottom: 420 }, 1280)).toMatchObject({ bottom: "calc(100dvh - 394px)" });
    expect(tooltipPosition({ ...chip, left: 0 }, 300)).toMatchObject({ left: 8, width: 284 });
  });

  it("önizleme Markdown işaretlerini temizler, kısaltır", () => {
    expect(plainExcerpt("In K8s, _namespaces_ hold [Lease](/docs/x) and `default` snake_case_name.")).toBe(
      "In K8s, namespaces hold Lease and default snake_case_name.",
    );
    expect(plainExcerpt("abcdef", 3)).toBe("abc…");
  });

  it("belge verisinden gelen adres yalnızca http(s) olabilir", () => {
    expect(safeHttpUrl("https://a.test/x")).toBe("https://a.test/x");
    expect(safeHttpUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeHttpUrl("data:text/html,x")).toBeUndefined();
    expect(safeHttpUrl("göreli/yol")).toBeUndefined();
    expect(safeHttpUrl(undefined)).toBeUndefined();
  });
});
