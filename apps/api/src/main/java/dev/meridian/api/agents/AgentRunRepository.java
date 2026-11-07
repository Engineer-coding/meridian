package dev.meridian.api.agents;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/** Kiracı ve kullanıcı filtresi yok: çalıştırma kişiye özeldir, izolasyonu RLS sağlar. */
@Repository
@Transactional
class AgentRunRepository {

    record Run(UUID id, String goal, String status, String steps, String pending, String answer, String cited,
            String sources, String stopReason, String model, int tokens, OffsetDateTime createdAt) {
    }

    private static final String COLUMNS =
        "id, goal, status, steps::text, pending::text, answer, cited::text, sources::text, stop_reason, model, tokens, created_at";

    private static final RowMapper<Run> RUN = (rs, rowNum) -> new Run(rs.getObject("id", UUID.class),
        rs.getString("goal"), rs.getString("status"), rs.getString("steps"), rs.getString("pending"),
        rs.getString("answer"), rs.getString("cited"), rs.getString("sources"), rs.getString("stop_reason"),
        rs.getString("model"), rs.getInt("tokens"), rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcClient jdbc;

    AgentRunRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** API çökerse "running" kalan kayıt yeni çalıştırmayı sonsuza dek engellemesin. */
    void expireStale() {
        jdbc.sql("""
                UPDATE agent_runs SET status = 'interrupted', updated_at = now()
                WHERE status = 'running' AND updated_at < now() - interval '10 minutes'""")
            .update();
    }

    Run insert(UUID id, String goal) {
        return jdbc.sql("""
                INSERT INTO agent_runs (id, tenant_id, user_id, goal)
                VALUES (:id, current_tenant_id(), current_user_id(), :goal)
                RETURNING %s""".formatted(COLUMNS))
            .param("id", id)
            .param("goal", goal)
            .query(RUN)
            .single();
    }

    @Transactional(readOnly = true)
    Optional<Run> findById(UUID id) {
        return jdbc.sql("SELECT %s FROM agent_runs WHERE id = :id".formatted(COLUMNS))
            .param("id", id)
            .query(RUN)
            .optional();
    }

    @Transactional(readOnly = true)
    List<Run> findLatest(int limit) {
        return jdbc.sql("SELECT %s FROM agent_runs ORDER BY created_at DESC LIMIT :limit".formatted(COLUMNS))
            .param("limit", limit)
            .query(RUN)
            .list();
    }

    void appendStep(UUID id, String stepJson) {
        jdbc.sql("""
                UPDATE agent_runs SET steps = steps || jsonb_build_array(:step::jsonb), updated_at = now()
                WHERE id = :id""")
            .param("id", id)
            .param("step", stepJson)
            .update();
    }

    void markWaiting(UUID id, String pendingJson, int tokens) {
        jdbc.sql("""
                UPDATE agent_runs SET status = 'waiting_approval', pending = :pending::jsonb,
                       tokens = tokens + :tokens, updated_at = now()
                WHERE id = :id AND status = 'running'""")
            .param("id", id)
            .param("pending", pendingJson)
            .param("tokens", tokens)
            .update();
    }

    /**
     * Onay kararının kilidi: yalnızca bir istek kazanır, ikincisi boş döner. Durum tek sorguda değiştiği
     * için aynı anda gelen iki onay iki ticket üretemez.
     */
    Optional<Run> claimPending(UUID id) {
        return jdbc.sql("""
                UPDATE agent_runs SET status = 'running', updated_at = now()
                WHERE id = :id AND status = 'waiting_approval'
                RETURNING %s""".formatted(COLUMNS))
            .param("id", id)
            .query(RUN)
            .optional();
    }

    void clearPending(UUID id, String stepJson) {
        jdbc.sql("""
                UPDATE agent_runs SET pending = NULL, steps = steps || jsonb_build_array(:step::jsonb), updated_at = now()
                WHERE id = :id""")
            .param("id", id)
            .param("step", stepJson)
            .update();
    }

    void finish(UUID id, String status, String answer, String cited, String sources, String stopReason, String model,
            int tokens) {
        jdbc.sql("""
                UPDATE agent_runs SET status = :status, answer = :answer, cited = :cited::jsonb, sources = :sources::jsonb,
                       stop_reason = :stopReason, model = :model, tokens = tokens + :tokens, updated_at = now()
                WHERE id = :id AND status = 'running'""")
            .param("id", id)
            .param("status", status)
            .param("answer", answer)
            .param("cited", cited)
            .param("sources", sources)
            .param("stopReason", stopReason)
            .param("model", model)
            .param("tokens", tokens)
            .update();
    }

    void interrupt(UUID id, int tokens) {
        jdbc.sql("""
                UPDATE agent_runs SET status = 'interrupted', tokens = tokens + :tokens, updated_at = now()
                WHERE id = :id AND status = 'running'""")
            .param("id", id)
            .param("tokens", tokens)
            .update();
    }

    void insertTicket(UUID id, UUID runId, String title, String description) {
        jdbc.sql("""
                INSERT INTO tickets (id, tenant_id, created_by, agent_run_id, title, description)
                VALUES (:id, current_tenant_id(), current_user_id(), :run, :title, :description)""")
            .param("id", id)
            .param("run", runId)
            .param("title", title)
            .param("description", description)
            .update();
    }
}
