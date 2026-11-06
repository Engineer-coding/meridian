package dev.meridian.api.identity;

import java.io.IOException;
import java.util.UUID;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.HandlerExceptionResolver;

import dev.meridian.api.apikeys.ApiKeyScopes;
import dev.meridian.api.apikeys.ApiKeyService;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * {@code X-API-Key} başlığını doğrular. Anahtar yalnızca adresindeki kiracıda aranır: başka kiracının
 * anahtarı ve bilinmeyen anahtar aynı 401'i alır. Üyelik ve rol denetimi sonraki filtrede ve servislerde
 * oturumla aynı yoldan geçer; anahtar, oluşturan kullanıcının rolünü aşamaz, kapsamı onu yalnızca daraltır.
 */
class ApiKeyFilter extends OncePerRequestFilter {

    static final String HEADER = "X-API-Key";

    private final ApiKeyService keys;
    private final HandlerExceptionResolver errors;

    ApiKeyFilter(ApiKeyService keys, HandlerExceptionResolver errors) {
        this.keys = keys;
        this.errors = errors;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String secret = request.getHeader(HEADER);
        if (secret == null || request.getHeader(HttpHeaders.AUTHORIZATION) != null) {
            chain.doFilter(request, response);
            return;
        }

        String path = request.getRequestURI();
        UUID tenantId = TenantContextFilter.tenantIdFromPath(path);
        var principal = tenantId == null
            ? java.util.Optional.<ApiKeyService.Principal>empty()
            : TenantContext.callAs(new Identity(null, tenantId), () -> keys.authenticate(secret));
        if (principal.isEmpty()) {
            reject(request, response, HttpStatus.UNAUTHORIZED);
            return;
        }

        String rest = path.substring(path.indexOf(tenantId.toString()) + tenantId.toString().length());
        if (!ApiKeyScopes.allows(principal.get().scopes(), request.getMethod(), rest)) {
            reject(request, response, HttpStatus.FORBIDDEN);
            return;
        }

        SecurityContextHolder.getContext().setAuthentication(new ApiKeyAuthentication(principal.get()));
        chain.doFilter(request, response);
    }

    private void reject(HttpServletRequest request, HttpServletResponse response, HttpStatus status) {
        errors.resolveException(request, response, null, new ResponseStatusException(status));
    }
}
