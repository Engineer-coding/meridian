import { headers } from "next/headers";

import { pickLocale, translate } from "@/i18n/messages";

export default async function SignedOut({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const locale = pickLocale((await headers()).get("accept-language"));
  const { error } = await searchParams;
  return (
    <main className="center">
      <div className="card">
        <h1>{translate(locale, error ? "signedOutError" : "signedOutTitle")}</h1>
        <a className="btn btn-primary" href="/auth/login">
          {translate(locale, "signIn")}
        </a>
      </div>
    </main>
  );
}
