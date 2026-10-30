package dev.meridian.api.tenancy;

import java.util.UUID;

public record Membership(UUID tenantId, String tenantName, String role) {
}