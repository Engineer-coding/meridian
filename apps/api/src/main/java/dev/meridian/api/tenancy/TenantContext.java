package dev.meridian.api.tenancy;

import java.util.Optional;
import java.util.UUID;
import java.util.function.Supplier;

/**
 * İstek boyunca geçerli kimlik bağlamı; her veritabanı işleminin başında PostgreSQL'e
 * aktarılır (ADR-0002). ScopedValue, bağlamın blok bitince kendiliğinden kalkmasını ve
 * aynı thread'i kullanan başka bir isteğe sızmamasını garanti eder.
 */
public final class TenantContext {

    /** {@code tenantId} boş olabilir: kullanıcı henüz kiracı seçmemiştir (ör. /v1/me). */
    public record Identity(UUID userId, UUID tenantId) {
    }

    /** Kontrollü istisna fırlatabilen iş (ör. servlet filtre zinciri). */
    @FunctionalInterface
    public interface CheckedAction<X extends Exception> {
        void run() throws X;
    }

    private static final ScopedValue<Identity> CURRENT = ScopedValue.newInstance();

    private TenantContext() {
    }

    public static Optional<Identity> current() {
        return CURRENT.isBound() ? Optional.of(CURRENT.get()) : Optional.empty();
    }

    public static <T> T callAs(Identity identity, Supplier<T> action) {
        return ScopedValue.where(CURRENT, identity).call(action::get);
    }

    public static void runAs(Identity identity, Runnable action) {
        ScopedValue.where(CURRENT, identity).run(action);
    }

    public static <X extends Exception> void runChecked(Identity identity, CheckedAction<X> action) throws X {
        ScopedValue.where(CURRENT, identity).call(() -> {
            action.run();
            return null;
        });
    }
}