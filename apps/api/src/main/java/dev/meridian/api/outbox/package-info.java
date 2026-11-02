/**
 * Transactional outbox (ADR-0004): olaylar iş kaydıyla aynı işlemde yazılır, ayrı bir
 * aktarıcı onları RabbitMQ'ya yayımlar. Hiçbir iş modülüne bağımlı değildir.
 */
@ApplicationModule(displayName = "Outbox", allowedDependencies = {})
package dev.meridian.api.outbox;

import org.springframework.modulith.ApplicationModule;
