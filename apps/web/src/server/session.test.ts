// @vitest-environment node
import { describe, expect, it } from "vitest";

import { MAX_COOKIE_BYTES, seal, unseal, type Session } from "./session";

const SECRET = "x".repeat(32);
const session: Session = { accessToken: "a.b.c", refreshToken: "r", expiresAt: 123 };

describe("oturum çerezi", () => {
  it("şifreler ve geri açar; token düz metin olarak görünmez", async () => {
    const token = await seal({ ...session, accessToken: "gizli-token" }, SECRET, 60);

    expect(token).not.toContain("gizli-token");
    expect(atob(token.split(".")[0]!)).toContain("A256GCM");
    expect(await unseal<Session>(token, SECRET)).toMatchObject({ accessToken: "gizli-token" });
  });

  it("başka anahtarla, bozulmuş ya da boş çerezi reddeder", async () => {
    const token = await seal(session, SECRET, 60);

    expect(await unseal(token, "y".repeat(32))).toBeNull();
    expect(await unseal(`${token}x`, SECRET)).toBeNull();
    expect(await unseal(undefined, SECRET)).toBeNull();
  });

  it("süresi dolmuş çerezi reddeder", async () => {
    expect(await unseal(await seal(session, SECRET, -1), SECRET)).toBeNull();
  });

  it("tarayıcının sessizce atacağı büyüklükte çerez üretmez", async () => {
    const big = { ...session, accessToken: "x".repeat(MAX_COOKIE_BYTES) };
    await expect(seal(big, SECRET, 60)).rejects.toThrow(/çok büyük/);
  });
});
