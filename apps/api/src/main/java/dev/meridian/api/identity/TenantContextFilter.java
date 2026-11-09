package dev.meridian.api.identity;

import java.io.IOException;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.HandlerExceptionResolver;

import dev.meridian.api.tenancy.MembershipRepository;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * JWT'deki kullanıcıyı ve adresteki kiracıyı {@link TenantContext}'e bağlar.
 *
 * <p>RLS, {@code app.tenant_id} değerine koşulsuz güvenir; güven sınırı bu değeri kimin
 * yazdığıdır. Bu yüzden kiracı ancak kullanıcının o kiracıdaki üyeliği doğrulandıktan sonra
 * bağlama yazılır. Üyelik yoksa, var olmayan kiracıyla aynı 404 döner: kiracının varlığı
 * sızdırılmaz.
 */
class TenantContextFilter extends OncePerRequestFilter {

    private static final Pattern TENANT_PATH = Pattern.compile(
        "^/v1/tenants/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(/.*)?$");

    static final String TENANT_MDC = "tenant.id";

    private final MembershipRepository memberships;
    private final HandlerExceptionResolver errors;

    TenantContextFilter(MembershipRepository memberships, HandlerExceptionResolver errors) {
        this.memberships = memberships;
        this.errors = errors;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        UUID userId;
        UUID apiKeyId = null;
        switch (SecurityContextHolder.getContext().getAuthentication()) {
            case JwtAuthenticationToken jwt -> {
                try {
                    userId = UUID.fromString(jwt.getToken().getSubject());
                } catch (IllegalArgumentException | NullPointerException e) {
                    reject(request, response, HttpStatus.UNAUTHORIZED);
                    return;
                }
            }
            // Anahtar, oluşturan kullanıcı adına çalışır: üyeliği kalkarsa anahtar da çalışmaz.
            case ApiKeyAuthentication key -> {
                userId = key.getPrincipal().userId();
                apiKeyId = key.getPrincipal().apiKeyId();
            }
            case null, default -> {
                chain.doFilter(request, response);
                return;
            }
        }

        UUID tenantId = tenantIdFromPath(request.getRequestURI());
        if (tenantId != null) {
            boolean member = TenantContext.callAs(new Identity(userId, null),
                () -> memberships.findRole(tenantId).isPresent());
            if (!member) {
                reject(request, response, HttpStatus.NOT_FOUND);
                return;
            }
        }

        // Kimlik değil yalnızca kiracı: log satırı ve iz kişiye işaret etmez.
        if (tenantId != null) {
            MDC.put(TENANT_MDC, tenantId.toString());
        }
        try {
            TenantContext.runChecked(new Identity(userId, tenantId, apiKeyId), () -> chain.doFilter(request, response));
        } catch (IOException | ServletException | RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new ServletException(e);
        } finally {
            MDC.remove(TENANT_MDC);
        }
    }

    static UUID tenantIdFromPath(String path) {
        Matcher m = TENANT_PATH.matcher(path);
        return m.matches() ? UUID.fromString(m.group(1)) : null;
    }

    /** Hata cevabını controller'larla aynı yoldan (problem+json) üretir. */
    private void reject(HttpServletRequest request, HttpServletResponse response, HttpStatus status) {
        errors.resolveException(request, response, null, new ResponseStatusException(status));
    }
}