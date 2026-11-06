package dev.meridian.api.identity;

import java.util.List;

import org.springframework.security.authentication.AbstractAuthenticationToken;

import dev.meridian.api.apikeys.ApiKeyService;

/** Doğrulanmış API anahtarı; gizli değeri taşımaz. */
final class ApiKeyAuthentication extends AbstractAuthenticationToken {

    private final transient ApiKeyService.Principal principal;

    ApiKeyAuthentication(ApiKeyService.Principal principal) {
        super(List.of());
        this.principal = principal;
        setAuthenticated(true);
    }

    @Override
    public Object getCredentials() {
        return "";
    }

    @Override
    public ApiKeyService.Principal getPrincipal() {
        return principal;
    }
}
