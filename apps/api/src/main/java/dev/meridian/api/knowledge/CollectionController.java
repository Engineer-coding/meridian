package dev.meridian.api.knowledge;

import java.util.List;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;

import dev.meridian.api.contract.api.CollectionsApi;
import dev.meridian.api.contract.model.CreateCollectionRequest;

/** OpenAPI sözleşmesinden üretilen {@link CollectionsApi} arayüzünü uygular. */
@RestController
class CollectionController implements CollectionsApi {

    private final CollectionService service;
    private final CollectionRepository collections;

    CollectionController(CollectionService service, CollectionRepository collections) {
        this.service = service;
        this.collections = collections;
    }

    @Override
    public ResponseEntity<dev.meridian.api.contract.model.Collection> createCollection(
            String idempotencyKey, UUID tenantId, CreateCollectionRequest request) {
        Collection collection = service.create(idempotencyKey, request.getName());
        return ResponseEntity.status(HttpStatus.CREATED).body(toApi(collection));
    }

    @Override
    public ResponseEntity<List<dev.meridian.api.contract.model.Collection>> listCollections(UUID tenantId) {
        return ResponseEntity.ok(collections.findAll().stream().map(CollectionController::toApi).toList());
    }

    private static dev.meridian.api.contract.model.Collection toApi(Collection collection) {
        return new dev.meridian.api.contract.model.Collection(collection.id(), collection.name(), collection.createdAt());
    }
}
