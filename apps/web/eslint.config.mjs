import next from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  { ignores: [".next/**", "src/lib/api/schema.d.ts", "playwright-report/**", "test-results/**", "next-env.d.ts"] },
  ...next,
  ...nextTs,
];

export default config;
