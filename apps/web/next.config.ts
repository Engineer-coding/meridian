import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Sıkıştırma SSE akışını tamponlayabilir; üretimde sıkıştırmayı ters vekil yapar.
  compress: false,
  // Konteyner imajı kendi kendine yeten sunucuyla derlenir (Dockerfile); `next start` akışı değişmez.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
};

export default config;
