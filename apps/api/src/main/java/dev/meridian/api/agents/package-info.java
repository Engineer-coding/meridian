/** Ajan: çalıştırma kaydı, insan onayı ve onaydan sonra oluşan ticket; döngü AI servisindedir (ADR-0015). */
@ApplicationModule(displayName = "Ajanlar", allowedDependencies = {"ai", "audit", "usage", "tenancy", "contract"})
package dev.meridian.api.agents;

import org.springframework.modulith.ApplicationModule;
