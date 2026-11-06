package dev.meridian.api.audit;

import java.util.Set;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.tenancy.MembershipRepository;
import dev.meridian.api.tenancy.TenantContext;

/**
 * Bağlamdaki kullanıcının aktif kiracıdaki rolünü denetler. Üyelik zaten kiracı kapısında
 * doğrulanmıştır; burada yalnızca rolün bu işlem için yeterli olup olmadığına bakılır.
 * Reddedilen karar, işlem geri alındıktan sonra {@link DeniedHandler} tarafından kaydedilir.
 */
@Component
public class Policy {

    public static final Set<String> CONTRIBUTORS = Set.of("owner", "admin", "member");
    public static final Set<String> ADMINS = Set.of("owner", "admin");

    private final MembershipRepository memberships;

    Policy(MembershipRepository memberships) {
        this.memberships = memberships;
    }

    public void require(String action, Set<String> allowed) {
        var tenantId = TenantContext.current().orElseThrow().tenantId();
        String role = memberships.findRole(tenantId).orElse("");
        if (!allowed.contains(role)) {
            throw new Denied(action);
        }
    }

    static final class Denied extends ResponseStatusException {
        final String action;

        Denied(String action) {
            super(HttpStatus.FORBIDDEN, "Bu işlem için rolünüz yetkili değil");
            this.action = action;
        }
    }
}
