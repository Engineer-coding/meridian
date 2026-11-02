package dev.meridian.api.tenancy;

import java.net.URI;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.contract.api.TenantsApi;
import dev.meridian.api.contract.model.CreateTenantRequest;
import dev.meridian.api.tenancy.TenantContext.Identity;

/** OpenAPI sözleşmesinden üretilen {@link TenantsApi} arayüzünü uygular. */
@RestController
class TenantController implements TenantsApi {

    private final TenantRepository tenants;
    private final TenantOnboarding onboarding;

    TenantController(TenantRepository tenants, TenantOnboarding onboarding) {
        this.tenants = tenants;
        this.onboarding = onboarding;
    }

    @Override
    public ResponseEntity<dev.meridian.api.contract.model.Tenant> createTenant(
            String idempotencyKey, CreateTenantRequest request) {
        var jwt = ((JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication()).getToken();
        String email = jwt.getClaimAsString("email");
        if (email == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Token'da email bilgisi yok");
        }
        UUID userId = TenantContext.current().orElseThrow().userId();
        // Yeni kiracının kimliği burada üretilir ve işlem bu kiracının bağlamında açılır:
        // RLS'in WITH CHECK koşulu yalnızca bağlamdaki kiracıya yazmaya izin verir.
        Tenant tenant = TenantContext.callAs(new Identity(userId, UUID.randomUUID()),
            () -> onboarding.create(idempotencyKey, email, request.getSlug(), request.getName()));
        return ResponseEntity.created(URI.create("/v1/tenants/" + tenant.id())).body(toApi(tenant));
    }

    @Override
    public ResponseEntity<dev.meridian.api.contract.model.Tenant> getTenant(UUID tenantId) {
        return tenants.findById(tenantId)
            .map(tenant -> ResponseEntity.ok(toApi(tenant)))
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }

    private static dev.meridian.api.contract.model.Tenant toApi(Tenant tenant) {
        return new dev.meridian.api.contract.model.Tenant(tenant.id(), tenant.name(), tenant.slug(),
            dev.meridian.api.contract.model.Tenant.PlanEnum.fromValue(tenant.plan()), tenant.createdAt());
    }
}
