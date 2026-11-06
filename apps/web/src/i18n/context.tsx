"use client";

import { createContext, useCallback, useContext, type ReactNode } from "react";

import { translate, type Locale, type MessageKey } from "./messages";

const LocaleContext = createContext<Locale>("tr");

export function LocaleProvider({ locale, children }: { locale: Locale; children: ReactNode }) {
  return <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>;
}

export function useT() {
  const locale = useContext(LocaleContext);
  return useCallback(
    (key: MessageKey, params?: Record<string, string | number>) => translate(locale, key, params),
    [locale],
  );
}
