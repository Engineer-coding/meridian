/** Idempotency-Key kayıtları; hiçbir iş modülüne bağımlı değildir. */
@ApplicationModule(displayName = "Idempotency", allowedDependencies = {})
package dev.meridian.api.idempotency;

import org.springframework.modulith.ApplicationModule;
