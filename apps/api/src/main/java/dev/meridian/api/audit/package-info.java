/** Yetki kararları ve denetim izi: rol denetimi tek yerde, sonucu değiştirilemez kayıtta (ADR-0014). */
@ApplicationModule(displayName = "Denetim", allowedDependencies = {"tenancy", "contract"})
package dev.meridian.api.audit;

import org.springframework.modulith.ApplicationModule;
