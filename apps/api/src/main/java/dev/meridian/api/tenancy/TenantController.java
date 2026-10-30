package dev.meridian.api.tenancy;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
class TenantController {

    private final TenantRepository tenants;

    TenantController(TenantRepository tenants) {
        this.tenants = tenants;
    }

    @GetMapping("/v1/tenants/{tenantId}")
    Tenant getTenant(@PathVariable UUID tenantId) {
        return tenants.findById(tenantId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }
}