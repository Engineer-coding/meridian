package dev.meridian.api.knowledge;

import java.util.Set;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.tenancy.MembershipRepository;
import dev.meridian.api.tenancy.TenantContext;

/**
 * Bağlamdaki kullanıcının aktif kiracıdaki rolünü denetler. Üyelik zaten kiracı kapısında
 * doğrulanmıştır; burada yalnızca rolün bu işlem için yeterli olup olmadığına bakılır.
 */
@Component
class Roles {

    static final Set<String> CONTRIBUTORS = Set.of("owner", "admin", "member");
    static final Set<String> ADMINS = Set.of("owner", "admin");

    private final MembershipRepository memberships;

    Roles(MembershipRepository memberships) {
        this.memberships = memberships;
    }

    void require(Set<String> allowed) {
        var tenantId = TenantContext.current().orElseThrow().tenantId();
        String role = memberships.findRole(tenantId).orElse("");
        if (!allowed.contains(role)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Bu işlem için rolünüz yetkili değil");
        }
    }
}
