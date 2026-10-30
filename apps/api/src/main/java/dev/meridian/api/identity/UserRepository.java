package dev.meridian.api.identity;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
@Transactional
class UserRepository {

    private final JdbcClient jdbc;

    UserRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** İlk girişte kullanıcıyı oluşturur (JIT provisioning), sonrakilerde bilgilerini günceller. */
    void upsertCurrent(String email, String displayName) {
        jdbc.sql("""
                INSERT INTO users (id, email, display_name) VALUES (current_user_id(), :email, :displayName)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, display_name = EXCLUDED.display_name""")
            .param("email", email)
            .param("displayName", displayName)
            .update();
    }
}