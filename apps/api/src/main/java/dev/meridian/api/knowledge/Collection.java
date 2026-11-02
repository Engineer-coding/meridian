package dev.meridian.api.knowledge;

import java.time.OffsetDateTime;
import java.util.UUID;

public record Collection(UUID id, String name, OffsetDateTime createdAt) {
}
