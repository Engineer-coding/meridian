import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-ext-400.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-sans/latin-ext-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-ext-400.css";
import "./globals.css";

import type { Metadata } from "next";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { pickLocale } from "@/i18n/messages";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Meridian",
  description: "Belgelerinizden kaynak gösteren cevaplar",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = pickLocale((await headers()).get("accept-language"));
  return (
    <html lang={locale}>
      <body>
        <Providers locale={locale}>{children}</Providers>
      </body>
    </html>
  );
}
