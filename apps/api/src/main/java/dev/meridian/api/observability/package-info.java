/**
 * İzleme altyapısı (ADR-0017, ADR-0018): log satırlarının OpenTelemetry'ye aktarılması. İş kuralı içermez.
 */
@ApplicationModule(displayName = "İzleme", allowedDependencies = {})
package dev.meridian.api.observability;

import org.springframework.modulith.ApplicationModule;
