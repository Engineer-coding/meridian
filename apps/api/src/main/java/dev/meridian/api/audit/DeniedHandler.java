package dev.meridian.api.audit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Reddi burada kaydeder: istisna işlemi geri aldıktan sonra çalışır, yani kayıt kendi işleminde
 * kalıcı olur. Kayıt yazılamazsa kullanıcı yine 403 alır; karar değişmez.
 */
@RestControllerAdvice
// Spring ilk eşleşen tavsiyeyi kullanır; öncelik olmazsa genel problem+json işleyicisi araya girer.
@Order(Ordered.HIGHEST_PRECEDENCE)
class DeniedHandler {

    private static final Logger log = LoggerFactory.getLogger(DeniedHandler.class);

    private final AuditLog audit;

    DeniedHandler(AuditLog audit) {
        this.audit = audit;
    }

    @ExceptionHandler(Policy.Denied.class)
    ProblemDetail denied(Policy.Denied denied) {
        try {
            audit.denied(denied.action);
        } catch (DataAccessException e) {
            log.error("reddedilen karar denetim kaydına yazılamadı action={}", denied.action, e);
        }
        return denied.getBody();
    }
}
