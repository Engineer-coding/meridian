/** Bilgi: koleksiyonlar ve kaynaklar; indeksleme olayları outbox üzerinden yayımlanır (ADR-0004). */
@ApplicationModule(displayName = "Bilgi", allowedDependencies = {"tenancy", "idempotency", "outbox", "contract"})
package dev.meridian.api.knowledge;

import org.springframework.modulith.ApplicationModule;
