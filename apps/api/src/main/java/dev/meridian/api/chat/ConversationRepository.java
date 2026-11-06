package dev.meridian.api.chat;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/** Kiracı ve kullanıcı filtresi yok: ikisini de RLS zorlar, değerler bağlamdan okunur. */
@Repository
@Transactional
class ConversationRepository {

    record Conversation(UUID id, String title, OffsetDateTime createdAt) {
    }

    /** {@code sources} ve {@code cited} JSON metni olarak taşınır; biçimini denetleyici bilir. */
    record StoredMessage(UUID id, String role, String content, String status, String sources, String cited,
            boolean abstained, boolean degraded, String model, OffsetDateTime createdAt) {
    }

    private static final RowMapper<Conversation> CONVERSATION = (rs, rowNum) -> new Conversation(
        rs.getObject("id", UUID.class), rs.getString("title"), rs.getObject("created_at", OffsetDateTime.class));

    private static final RowMapper<StoredMessage> MESSAGE = (rs, rowNum) -> new StoredMessage(
        rs.getObject("id", UUID.class), rs.getString("role"), rs.getString("content"), rs.getString("status"),
        rs.getString("sources"), rs.getString("cited"), rs.getBoolean("abstained"), rs.getBoolean("degraded"),
        rs.getString("model"), rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcClient jdbc;

    ConversationRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    Conversation insert(UUID id, String title) {
        return jdbc.sql("""
                INSERT INTO conversations (id, tenant_id, user_id, title)
                VALUES (:id, current_tenant_id(), current_user_id(), :title)
                RETURNING id, title, created_at""")
            .param("id", id)
            .param("title", title)
            .query(CONVERSATION)
            .single();
    }

    @Transactional(readOnly = true)
    Optional<Conversation> findById(UUID id) {
        return jdbc.sql("SELECT id, title, created_at FROM conversations WHERE id = :id")
            .param("id", id)
            .query(CONVERSATION)
            .optional();
    }

    @Transactional(readOnly = true)
    List<Conversation> findLatest(int limit) {
        return jdbc.sql("SELECT id, title, created_at FROM conversations ORDER BY created_at DESC, id DESC LIMIT :limit")
            .param("limit", limit)
            .query(CONVERSATION)
            .list();
    }

    /** İlk soru başlık olur; başlık zaten varsa dokunmaz. */
    void titleIfMissing(UUID id, String title) {
        jdbc.sql("UPDATE conversations SET title = :title WHERE id = :id AND title IS NULL")
            .param("id", id)
            .param("title", title)
            .update();
    }

    void insertMessage(UUID id, UUID conversationId, String role, String content, String status, String sources,
            String cited, boolean abstained, boolean degraded, String model) {
        jdbc.sql("""
                INSERT INTO messages (id, tenant_id, user_id, conversation_id, role, content, status, sources, cited,
                                      abstained, degraded, model)
                VALUES (:id, current_tenant_id(), current_user_id(), :conversationId, :role, :content, :status,
                        :sources::jsonb, :cited::jsonb, :abstained, :degraded, :model)""")
            .param("id", id)
            .param("conversationId", conversationId)
            .param("role", role)
            .param("content", content)
            .param("status", status)
            .param("sources", sources)
            .param("cited", cited)
            .param("abstained", abstained)
            .param("degraded", degraded)
            .param("model", model)
            .update();
    }

    @Transactional(readOnly = true)
    List<StoredMessage> findMessages(UUID conversationId) {
        return jdbc.sql("""
                SELECT id, role, content, status, sources::text AS sources, cited::text AS cited, abstained, degraded,
                       model, created_at
                FROM messages WHERE conversation_id = :conversationId ORDER BY created_at, id""")
            .param("conversationId", conversationId)
            .query(MESSAGE)
            .list();
    }
}
