package dev.meridian.api.tenancy;

import java.util.UUID;

public record Tenant(UUID id, String slug, String name, String plan) {
}