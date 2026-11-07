/** Sohbet: kişiye özel konuşmalar ve AI servisinden akan kaynaklı cevaplar (ADR-0001, ADR-0008). */
@ApplicationModule(displayName = "Sohbet", allowedDependencies = {"ai", "tenancy", "audit", "usage", "idempotency", "contract"})
package dev.meridian.api.chat;

import org.springframework.modulith.ApplicationModule;
