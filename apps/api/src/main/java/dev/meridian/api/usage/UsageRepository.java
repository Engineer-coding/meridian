package dev.meridian.api.usage;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/** Kiracı filtresi yok: izolasyonu RLS sağlar. */
@Repository
@Transactional
class UsageRepository {

    record Day(LocalDate date, long tokens, long answers) {
    }

    record Totals(long estimatedTokens, BigDecimal costUsd) {
    }

    private final JdbcClient jdbc;

    UsageRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void insert(UUID id, UUID userId, String model, int promptTokens, int completionTokens, boolean estimated,
            BigDecimal costUsd) {
        jdbc.sql("""
                INSERT INTO usage_events (id, tenant_id, user_id, model, prompt_tokens, completion_tokens,
                                          estimated, cost_usd)
                VALUES (:id, current_tenant_id(), :user, :model, :prompt, :completion, :estimated, :cost)""")
            .param("id", id)
            .param("user", userId)
            .param("model", model)
            .param("prompt", promptTokens)
            .param("completion", completionTokens)
            .param("estimated", estimated)
            .param("cost", costUsd)
            .update();
    }

    @Transactional(readOnly = true)
    String plan() {
        return jdbc.sql("SELECT plan FROM tenants WHERE id = current_tenant_id()").query(String.class).single();
    }

    @Transactional(readOnly = true)
    long tokensSince(OffsetDateTime since) {
        return jdbc.sql("""
                SELECT coalesce(sum(prompt_tokens + completion_tokens), 0) FROM usage_events
                WHERE created_at >= :since""")
            .param("since", since)
            .query(Long.class)
            .single();
    }

    /** Yalnızca olayı olan günler; boşlukları çağıran doldurur. */
    @Transactional(readOnly = true)
    List<Day> daysSince(OffsetDateTime since) {
        return jdbc.sql("""
                SELECT (created_at AT TIME ZONE 'UTC')::date AS day,
                       sum(prompt_tokens + completion_tokens) AS tokens, count(*) AS answers
                FROM usage_events WHERE created_at >= :since
                GROUP BY day ORDER BY day""")
            .param("since", since)
            .query((rs, rowNum) -> new Day(rs.getObject("day", LocalDate.class), rs.getLong("tokens"),
                rs.getLong("answers")))
            .list();
    }

    @Transactional(readOnly = true)
    Totals totalsSince(OffsetDateTime since) {
        return jdbc.sql("""
                SELECT coalesce(sum(prompt_tokens + completion_tokens) FILTER (WHERE estimated), 0) AS estimated,
                       coalesce(sum(cost_usd), 0) AS cost
                FROM usage_events WHERE created_at >= :since""")
            .param("since", since)
            .query((rs, rowNum) -> new Totals(rs.getLong("estimated"), rs.getBigDecimal("cost")))
            .single();
    }
}
