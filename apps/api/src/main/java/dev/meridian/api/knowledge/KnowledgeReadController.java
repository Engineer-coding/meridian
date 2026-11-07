package dev.meridian.api.knowledge;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.ai.AiClient;
import dev.meridian.api.contract.api.KnowledgeApi;
import dev.meridian.api.contract.model.DocumentContent;
import dev.meridian.api.contract.model.SearchHit;
import dev.meridian.api.contract.model.SearchRequest;
import dev.meridian.api.contract.model.SearchResult;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.usage.RateLimiter;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** Tarayıcı dışı istemcilerin (MCP sunucusu dahil) okuma uçları; OpenAPI'den üretilen arayüzü uygular. */
@RestController
class KnowledgeReadController implements KnowledgeApi {

    private static final int MAX_DOCUMENT_CHUNKS = 200;

    private final AiClient ai;
    private final RateLimiter limiter;
    private final JdbcClient jdbc;
    private final JsonMapper json;
    private final int capacity;
    private final int refillPerMinute;

    KnowledgeReadController(AiClient ai, RateLimiter limiter, JdbcClient jdbc, JsonMapper json,
            @Value("${meridian.search.rate.capacity}") int capacity,
            @Value("${meridian.search.rate.refill-per-minute}") int refillPerMinute) {
        this.ai = ai;
        this.limiter = limiter;
        this.jdbc = jdbc;
        this.json = json;
        this.capacity = capacity;
        this.refillPerMinute = refillPerMinute;
    }

    @Override
    public ResponseEntity<SearchResult> searchKnowledge(UUID tenantId, SearchRequest request) {
        limiter.acquire("search", tenantId, TenantContext.current().orElseThrow().userId(), capacity, refillPerMinute);
        var body = new LinkedHashMap<String, Object>();
        body.put("tenantId", tenantId);
        body.put("query", request.getQuery());
        body.put("k", request.getK() == null ? 5 : request.getK());
        if (request.getCollectionIds() != null && !request.getCollectionIds().isEmpty()) {
            body.put("collectionIds", request.getCollectionIds());
        }
        try {
            JsonNode result = ai.call("/internal/v1/search", body);
            return ResponseEntity.ok(new SearchResult(
                json.convertValue(result.get("hits"), new TypeReference<ArrayList<SearchHit>>() { })));
        } catch (AiClient.Unavailable e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Arama şu an kullanılamıyor", e);
        }
    }

    @Override
    @Transactional(readOnly = true)
    public ResponseEntity<DocumentContent> getDocument(String path, UUID tenantId) {
        var header = jdbc.sql("""
                SELECT id, title, url FROM documents WHERE path = :path ORDER BY indexed_at DESC LIMIT 1""")
            .param("path", path)
            .query((rs, rowNum) -> new Object[] {rs.getObject("id", UUID.class), rs.getString("title"), rs.getString("url")})
            .optional()
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        var content = jdbc.sql("""
                SELECT content FROM chunks WHERE document_id = :id ORDER BY ordinal LIMIT :limit""")
            .param("id", header[0])
            .param("limit", MAX_DOCUMENT_CHUNKS)
            .query(String.class)
            .list();
        return ResponseEntity.ok(new DocumentContent(path, (String) header[1], String.join("\n\n", content))
            .url((String) header[2]));
    }
}
