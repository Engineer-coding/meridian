import { z } from "zod";

const schema = z.object({
  APP_URL: z.url(),
  API_URL: z.url(),
  OIDC_ISSUER: z.url(),
  OIDC_CLIENT_ID: z.string().min(1),
  // Kısa bir sır çerezi şifreleyen anahtarı zayıflatır; varsayılan değer bilerek yok.
  SESSION_SECRET: z.string().min(32),
});

export type Env = z.infer<typeof schema>;

/** Derleme sırasında değil, ilk istekte okunur: imaj ortamdan bağımsız kalır. */
export function env(): Env {
  return schema.parse(process.env);
}
