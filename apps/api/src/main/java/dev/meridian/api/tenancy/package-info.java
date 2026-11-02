/** Kiracılık: kiracılar, üyelikler ve kiracı bağlamının veritabanına aktarılması (ADR-0002). */
@ApplicationModule(displayName = "Kiracılık", allowedDependencies = {"idempotency", "contract"})
package dev.meridian.api.tenancy;

import org.springframework.modulith.ApplicationModule;
