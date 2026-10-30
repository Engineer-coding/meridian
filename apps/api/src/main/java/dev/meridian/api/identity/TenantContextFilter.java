package dev.meridian.api.identity;

import java.io.IOException;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

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

    private final MembershipRepository memberships;
    private final HandlerExceptionResolver errors;

    TenantContextFilter(MembershipRepository memberships, HandlerExceptionResolver errors) {
        this.memberships = memberships;
        this.errors = errors;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (!(SecurityContextHolder.getContext().getAuthentication() instanceof JwtAuthenticationToken jwt)) {
            chain.doFilter(request, response);
            return;
        }

        UUID userId;
        try {
            userId = UUID.fromString(jwt.getToken().getSubject());
        } catch (IllegalArgumentException | NullPointerException e) {
            reject(request, response, HttpStatus.UNAUTHORIZED);
            return;
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

        try {
            TenantContext.runChecked(new Identity(userId, tenantId), () -> chain.doFilter(request, response));
        } catch (IOException | ServletException | RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new ServletException(e);
        }
    }

    private static UUID tenantIdFromPath(String path) {
        Matcher m = TENANT_PATH.matcher(path);
        return m.matches() ? UUID.fromString(m.group(1)) : null;
    }

    /** Hata cevabını controller'larla aynı yoldan (problem+json) üretir. */
    private void reject(HttpServletRequest request, HttpServletResponse response, HttpStatus status) {
        errors.resolveException(request, response, null, new ResponseStatusException(status));
    }
}