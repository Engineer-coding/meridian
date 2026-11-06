// @vitest-environment node
import { describe, expect, it } from "vitest";

import { isAllowedOrigin, requestHeaders, responseHeaders, upstreamUrl } from "./proxy";

const APP = "http://localhost:3000";
const API = "http://localhost:8080";

describe("API vekili", () => {
  it("başka kökenden gelen durum değiştiren isteği reddeder (CSRF)", () => {
    expect(isAllowedOrigin("POST", "https://evil.test", APP)).toBe(false);
    expect(isAllowedOrigin("POST", null, APP)).toBe(false);
    expect(isAllowedOrigin("DELETE", "https://evil.test", APP)).toBe(false);
    expect(isAllowedOrigin("POST", APP, APP)).toBe(true);
    expect(isAllowedOrigin("GET", null, APP)).toBe(true);
  });

  it("/v1 öneki dışına çıkılamaz", () => {
    expect(upstreamUrl(API, ["..", "actuator", "env"], "")).toBeNull();
    expect(upstreamUrl(API, ["tenants", "..", "..", "x"], "")).toBeNull();
    expect(upstreamUrl(API, ["a/b"], "")).toBeNull();
    expect(upstreamUrl(API, ["a\\b"], "")).toBeNull();
    expect(upstreamUrl(API, ["me"], "?a=1")?.href).toBe("http://localhost:8080/v1/me?a=1");
  });

  it("çerezi ve istemcinin Authorization başlığını API'ye geçirmez", () => {
    const headers = requestHeaders(
      new Headers({ Cookie: "meridian_session=x", Authorization: "Bearer sahte", "Content-Type": "application/json" }),
      "gercek",
    );

    expect(headers.get("authorization")).toBe("Bearer gercek");
    expect(headers.get("cookie")).toBeNull();
    expect(headers.get("content-type")).toBe("application/json");
  });

  it("akış cevabının tamponlanmasını engeller; yalnızca bilinen başlıkları geçirir", () => {
    const headers = responseHeaders(new Headers({ "Content-Type": "text/event-stream", "Set-Cookie": "x=1", "Retry-After": "3" }));

    expect(headers.get("cache-control")).toContain("no-transform");
    expect(headers.get("x-accel-buffering")).toBe("no");
    expect(headers.get("retry-after")).toBe("3");
    expect(headers.get("set-cookie")).toBeNull();
  });
});
