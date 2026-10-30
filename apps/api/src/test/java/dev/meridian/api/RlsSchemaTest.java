package dev.meridian.api;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

/** ADR-0002'nin şema ve rol güvencelerini doğrular. */
class RlsSchemaTest extends PostgresIntegrationTest {

    @Test
    void everyCoreTableHasForcedRowLevelSecurity() throws Exception {
        List<String> unprotected = queryAsSuperuser("""
            SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'core' AND c.relkind = 'r' AND c.relname <> 'flyway_schema_history'
              AND NOT (c.relrowsecurity AND c.relforcerowsecurity)""");
        assertThat(unprotected).as("RLS veya FORCE eksik tablolar").isEmpty();
    }

    @Test
    void appRoleCannotBypassRowLevelSecurity() throws Exception {
        assertThat(queryAsSuperuser(
            "SELECT (rolsuper OR rolbypassrls)::text FROM pg_roles WHERE rolname = 'meridian_app'"))
            .containsExactly("false");
    }

    @Test
    void appRoleDoesNotOwnAnyTable() throws Exception {
        assertThat(queryAsSuperuser("""
            SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'core' AND pg_get_userbyid(c.relowner) = 'meridian_app'"""))
            .as("uygulama rolünün sahibi olduğu tablolar").isEmpty();
    }
}