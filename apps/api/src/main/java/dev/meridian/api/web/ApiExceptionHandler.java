package dev.meridian.api.web;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** Spring'in kendi problem+json işleyicisinin kapsamadığı veri katmanı hataları. */
@RestControllerAdvice
class ApiExceptionHandler {

    /** Benzersizlik ihlali (ör. kullanımda olan slug): 500 değil 409. */
    @ExceptionHandler(DuplicateKeyException.class)
    ProblemDetail duplicate() {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "Bu değer başka bir kayıt tarafından kullanılıyor");
    }
}
