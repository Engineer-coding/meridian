import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Sıkıştırma SSE akışını tamponlayabilir; üretimde sıkıştırmayı ters vekil yapar.
  compress: false,
};

export default config;
