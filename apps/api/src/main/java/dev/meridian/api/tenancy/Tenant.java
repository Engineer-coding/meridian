package dev.meridian.api.tenancy;

import java.time.OffsetDateTime;
import java.util.UUID;

public record Tenant(UUID id, String slug, String name, String plan, OffsetDateTime createdAt) {
}
