package dev.meridian.api.knowledge;

import java.net.URI;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.contract.api.SourcesApi;
import dev.meridian.api.contract.model.CreateSourceRequest;
import dev.meridian.api.contract.model.GithubSourceConfig;
import dev.meridian.api.contract.model.SourceConfig;
import dev.meridian.api.contract.model.SourcePage;
import dev.meridian.api.contract.model.SourceStatus;
import dev.meridian.api.contract.model.SourceType;
import dev.meridian.api.contract.model.UploadSourceConfig;
import dev.meridian.api.contract.model.WebSourceConfig;

/**
 * OpenAPI sözleşmesinden üretilen {@link SourcesApi} arayüzünü uygular. Adresteki
 * {@code tenantId} burada kullanılmaz: kiracı kapısı onu doğrulayıp bağlama yazmıştır ve
 * sorgular kiracıyı bağlamdan okur.
 */
@RestController
class SourceController implements SourcesApi {

    private final SourceService service;
    private final SourceRepository sources;

    SourceController(SourceService service, SourceRepository sources) {
        this.service = service;
        this.sources = sources;
    }

    @Override
    public ResponseEntity<dev.meridian.api.contract.model.Source> createSource(
            String idempotencyKey, UUID tenantId, CreateSourceRequest request) {
        Source source = service.create(idempotencyKey, request.getCollectionId(), request.getName(),
            canonical(request.getConfig()));
        return ResponseEntity.accepted()
            .location(URI.create("/v1/tenants/" + tenantId + "/sources/" + source.id()))
            .body(toApi(source));
    }

    @Override
    public ResponseEntity<SourcePage> listSources(UUID tenantId, String cursor, Integer limit) {
        int size = limit == null ? 20 : limit;
        // Bir fazlası istenir: dönerse sonraki sayfa vardır.
        List<Source> rows = sources.findPage(cursor == null ? null : SourceCursor.decode(cursor), size + 1);
        List<Source> page = rows.subList(0, Math.min(size, rows.size()));
        var body = new SourcePage(page.stream().map(SourceController::toApi).toList());
        body.setNextCursor(rows.size() > size ? SourceCursor.of(page.getLast()).encode() : null);
        return ResponseEntity.ok(body);
    }

    @Override
    public ResponseEntity<dev.meridian.api.contract.model.Source> getSource(UUID tenantId, UUID sourceId) {
        return sources.findById(sourceId)
            .map(source -> ResponseEntity.ok(toApi(source)))
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }

    @Override
    public ResponseEntity<Void> deleteSource(UUID tenantId, UUID sourceId) {
        service.delete(sourceId);
        return ResponseEntity.accepted().build();
    }

    /**
     * Yapılandırmanın varsayılanları doldurulmuş, alan sırası sabit hâli. Aynı istek her
     * seferinde aynı JSON'a dönüşür; idempotency parmak izi ve olay içeriği buna dayanır.
     */
    private static Map<String, Object> canonical(SourceConfig config) {
        var map = new LinkedHashMap<String, Object>();
        switch (config) {
            case UploadSourceConfig upload -> map.put("type", "upload");
            case WebSourceConfig web -> {
                map.put("type", "web");
                map.put("startUrl", web.getStartUrl().toString());
                map.put("maxPages", web.getMaxPages() == null ? 100 : web.getMaxPages());
            }
            case GithubSourceConfig github -> {
                map.put("type", "github");
                map.put("repository", github.getRepository());
                map.put("branch", github.getBranch() == null ? "main" : github.getBranch());
                map.put("paths", github.getPaths() == null ? List.of() : List.copyOf(github.getPaths()));
            }
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Bilinmeyen kaynak türü");
        }
        return map;
    }

    private static dev.meridian.api.contract.model.Source toApi(Source source) {
        var api = new dev.meridian.api.contract.model.Source(source.id(), source.name(), source.collectionId(),
            SourceType.fromValue(source.type()), SourceStatus.fromValue(source.status()), source.createdAt());
        api.setDocumentCount(source.documentCount());
        api.setLastIndexedAt(source.lastIndexedAt());
        api.setLastError(source.lastError());
        return api;
    }
}
