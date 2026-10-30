package dev.meridian.api.tenancy;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.UUID;

import javax.sql.DataSource;

import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.TransactionDefinition;

/**
 * Her işlemin başında kimlik bağlamını PostgreSQL'e yazar. {@code set_config(..., true)}
 * işleme yereldir: commit/rollback sonrası silinir ve havuzdaki bağlantıyla bir sonraki
 * isteğe taşınmaz (ADR-0002, tuzak 2). Bağlam yoksa boş değer yazılır; politikalar
 * bunu NULL'a çevirir ve hiçbir satır döndürmez (tuzak 3).
 */
public class TenantAwareTransactionManager extends JdbcTransactionManager {

    private static final String SET_CONTEXT =
        "SELECT set_config('app.user_id', ?, true), set_config('app.tenant_id', ?, true)";

    public TenantAwareTransactionManager(DataSource dataSource) {
        super(dataSource);
    }

    @Override
    protected void prepareTransactionalConnection(Connection con, TransactionDefinition definition)
            throws SQLException {
        super.prepareTransactionalConnection(con, definition);
        var identity = TenantContext.current();
        try (PreparedStatement ps = con.prepareStatement(SET_CONTEXT)) {
            ps.setString(1, identity.map(i -> text(i.userId())).orElse(""));
            ps.setString(2, identity.map(i -> text(i.tenantId())).orElse(""));
            ps.execute();
        }
    }

    private static String text(UUID id) {
        return id == null ? "" : id.toString();
    }
}