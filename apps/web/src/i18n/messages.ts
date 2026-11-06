export const LOCALES = ["tr", "en"] as const;
export type Locale = (typeof LOCALES)[number];

const tr = {
  answerLabel: "Cevap",
  abstained: "Bu sorunun cevabını kaynaklarda doğrulayamadım. Aşağıda aranan kaynakları görebilirsiniz.",
  apiDown: "Sunucuya ulaşılamıyor.",
  citationLabel: "Kaynak {number}: {title}",
  citationMissing: "Bu numarada bir kaynak yok",
  conversations: "Konuşmalar",
  createTenant: "Çalışma alanı oluştur",
  degraded: "Cevap şu an üretilemiyor. Aranan kaynaklar aşağıda.",
  disclaimer: "Cevaplar yapay zekâ ile üretilir; önemli konularda kaynağı kontrol edin.",
  emptyBody: "Cevaplar yalnızca çalışma alanınızdaki belgelerden, kaynak gösterilerek üretilir.",
  emptyTitle: "Belgelerinize bir soru sorun",
  failed: "Bir şeyler ters gitti.",
  interrupted: "Cevap yarıda kesildi.",
  loading: "Yükleniyor…",
  newConversation: "Yeni konuşma",
  noConversations: "Henüz konuşma yok.",
  onboardingBody: "Başlamak için bir çalışma alanı oluşturun.",
  onboardingTitle: "Hoş geldiniz",
  questionLabel: "Sorunuz",
  questionPlaceholder: "Sorunuzu yazın. Göndermek için Enter, yeni satır için Shift+Enter.",
  rateLimited: "Çok fazla soru gönderildi. {seconds} saniye sonra yeniden deneyin.",
  regenerate: "Yeniden üret",
  retry: "Yeniden dene",
  send: "Gönder",
  signOut: "Çıkış",
  skipToQuestion: "Soru alanına geç",
  sourceCited: "cevapta kullanıldı",
  sourcesTitle: "{count} kaynak",
  statusSearching: "Kaynaklar aranıyor…",
  statusWaiting: "Kaynaklar bulundu, model cevabı hazırlıyor. Bu yaklaşık bir dakika sürebilir.",
  stop: "Durdur",
  signedOutTitle: "Çıkış yaptınız",
  signedOutError: "Giriş tamamlanamadı. Lütfen yeniden deneyin.",
  signIn: "Giriş yap",
  tenantConflict: "Bu kısa ad kullanılıyor.",
  tenantName: "Çalışma alanı adı",
  tenantNameError: "En az 2, en fazla 100 karakter olmalı.",
  tenantSlug: "Kısa ad",
  tenantSlugError: "Küçük harf, rakam ve tire; 3–40 karakter.",
  untitled: "Adsız konuşma",
  workspace: "Çalışma alanı",
};

export type MessageKey = keyof typeof tr;

const en: Record<MessageKey, string> = {
  answerLabel: "Answer",
  abstained: "I couldn't verify an answer in the sources. The sources that were searched are listed below.",
  apiDown: "The server can't be reached.",
  citationLabel: "Source {number}: {title}",
  citationMissing: "There is no source with this number",
  conversations: "Conversations",
  createTenant: "Create workspace",
  degraded: "An answer can't be generated right now. The sources that were searched are listed below.",
  disclaimer: "Answers are AI-generated; check the source for anything important.",
  emptyBody: "Answers come only from the documents in your workspace, with citations.",
  emptyTitle: "Ask your documents a question",
  failed: "Something went wrong.",
  interrupted: "The answer was interrupted.",
  loading: "Loading…",
  newConversation: "New conversation",
  noConversations: "No conversations yet.",
  onboardingBody: "Create a workspace to get started.",
  onboardingTitle: "Welcome",
  questionLabel: "Your question",
  questionPlaceholder: "Type your question. Enter to send, Shift+Enter for a new line.",
  rateLimited: "Too many questions. Try again in {seconds} seconds.",
  regenerate: "Regenerate",
  retry: "Try again",
  send: "Send",
  signOut: "Sign out",
  skipToQuestion: "Skip to question",
  sourceCited: "used in the answer",
  sourcesTitle: "{count} sources",
  statusSearching: "Searching the sources…",
  statusWaiting: "Sources found, the model is preparing an answer. This can take about a minute.",
  stop: "Stop",
  signedOutTitle: "You've signed out",
  signedOutError: "Sign-in couldn't be completed. Please try again.",
  signIn: "Sign in",
  tenantConflict: "This short name is taken.",
  tenantName: "Workspace name",
  tenantNameError: "Must be 2 to 100 characters.",
  tenantSlug: "Short name",
  tenantSlugError: "Lowercase letters, digits and hyphens; 3 to 40 characters.",
  untitled: "Untitled conversation",
  workspace: "Workspace",
};

export const MESSAGES: Record<Locale, Record<MessageKey, string>> = { tr, en };

export function translate(locale: Locale, key: MessageKey, params?: Record<string, string | number>): string {
  return MESSAGES[locale][key].replace(/\{(\w+)\}/g, (_, name: string) => String(params?.[name] ?? `{${name}}`));
}

/** Kullanıcının tarayıcı dili; bilinmiyorsa Türkçe. */
export function pickLocale(acceptLanguage: string | null): Locale {
  const first = acceptLanguage?.split(",")[0]?.trim().slice(0, 2).toLowerCase();
  return first === "en" ? "en" : "tr";
}
