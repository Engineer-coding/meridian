package dev.meridian.api.knowledge;

import java.time.OffsetDateTime;
import java.util.UUID;

public record Source(UUID id, UUID collectionId, String name, String type, String status, int documentCount,
        OffsetDateTime lastIndexedAt, String lastError, OffsetDateTime createdAt) {
}
