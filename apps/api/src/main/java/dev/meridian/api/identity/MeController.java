package dev.meridian.api.identity;

import java.util.List;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.tenancy.Membership;
import dev.meridian.api.tenancy.MembershipRepository;

@RestController
class MeController {

    /** OpenAPI sözleşmesindeki {@code Me} şeması. */
    record Me(UUID id, String email, String displayName, List<Membership> memberships) {
    }

    private final UserRepository users;
    private final MembershipRepository memberships;

    MeController(UserRepository users, MembershipRepository memberships) {
        this.users = users;
        this.memberships = memberships;
    }

    @GetMapping("/v1/me")
    Me me(@AuthenticationPrincipal Jwt jwt) {
        String email = jwt.getClaimAsString("email");
        if (email == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Token'da email bilgisi yok");
        }
        String displayName = jwt.getClaimAsString("name");
        users.upsertCurrent(email, displayName);
        return new Me(UUID.fromString(jwt.getSubject()), email, displayName, memberships.findForCurrentUser());
    }
}