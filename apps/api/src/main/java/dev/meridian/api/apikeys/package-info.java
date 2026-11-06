/** API anahtarları: gizli değer özetiyle saklanır, her anahtarın kapsamı ve süresi vardır (ADR-0014). */
@ApplicationModule(displayName = "API anahtarları", allowedDependencies = {"tenancy", "audit", "contract"})
package dev.meridian.api.apikeys;

import org.springframework.modulith.ApplicationModule;
