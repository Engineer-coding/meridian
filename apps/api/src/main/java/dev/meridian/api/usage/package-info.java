/** Kullanım: kiracı başına token muhasebesi ve günlük kota (ADR-0014). */
@ApplicationModule(displayName = "Kullanım", allowedDependencies = {"tenancy", "audit", "contract"})
package dev.meridian.api.usage;

import org.springframework.modulith.ApplicationModule;
