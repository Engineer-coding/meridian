package dev.meridian.api.identity;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.contract.api.IdentityApi;
import dev.meridian.api.contract.model.Me;
import dev.meridian.api.contract.model.Membership;
import dev.meridian.api.contract.model.Role;
import dev.meridian.api.tenancy.MembershipRepository;

/** OpenAPI sözleşmesinden üretilen {@link IdentityApi} arayüzünü uygular. */
@RestController
class MeController implements IdentityApi {

    private final UserRepository users;
    private final MembershipRepository memberships;

    MeController(UserRepository users, MembershipRepository memberships) {
        this.users = users;
        this.memberships = memberships;
    }

    @Override
    public ResponseEntity<Me> getMe() {
        var jwt = ((JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication()).getToken();
        String email = jwt.getClaimAsString("email");
        if (email == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Token'da email bilgisi yok");
        }
        String displayName = jwt.getClaimAsString("name");
        users.upsertCurrent(email, displayName);
        var items = memberships.findForCurrentUser().stream()
            .map(m -> new Membership(m.tenantId(), m.tenantName(), Role.fromValue(m.role())))
            .toList();
        return ResponseEntity.ok(new Me(UUID.fromString(jwt.getSubject()), email, items).displayName(displayName));
    }
}
