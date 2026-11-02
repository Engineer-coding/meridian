-- Belgeler, parçalar (vektör + tam metin) ve işlenmiş olaylar (ADR-0003, ADR-0012).
-- Bu tablolara AI servisi (meridian_ai rolü) yazar; kiracı izolasyonu aynı RLS kuralıyla.

-- Belge ve parçaların kaynak/koleksiyon tutarlılığı şemada zorlanır (bkz. V3, tehdit T13):
-- bir belge yalnızca kendi kiracısının kaynağına ve o kaynağın koleksiyonuna bağlanabilir.
ALTER TABLE sources ADD CONSTRAINT sources_tenant_id_id_collection_key UNIQUE (tenant_id, id, collection_id);

CREATE TABLE documents (
    id            uuid        PRIMARY KEY,
    tenant_id     uuid        NOT NULL,
    collection_id uuid        NOT NULL,
    source_id     uuid        NOT NULL,
    path          text        NOT NULL,
    title         text        NOT NULL,
    url           text,
    -- Kaynağın sürümü (ör. git commit); aynı sürüm yeniden indekslenirse içerik değişmemiştir.
    version       text,
    content_hash  text        NOT NULL,
    chunk_count   integer     NOT NULL,
    indexed_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, path),
    UNIQUE (tenant_id, id, collection_id),
    FOREIGN KEY (tenant_id, source_id, collection_id)
        REFERENCES sources (tenant_id, id, collection_id) ON DELETE CASCADE
);

CREATE TABLE chunks (
    id            uuid        PRIMARY KEY,
    tenant_id     uuid        NOT NULL,
    collection_id uuid        NOT NULL,
    document_id   uuid        NOT NULL,
    ordinal       integer     NOT NULL,
    -- Başlık yolu, ör. "Pods > Pod lifecycle"; alıntı gösterimi ve tam metin araması için.
    section       text        NOT NULL,
    content       text        NOT NULL,
    -- 'simple': korpus çok dilli (tr/en); dile özgü kök bulma yanlış dilde kelimeleri bozar.
    content_tsv   tsvector    GENERATED ALWAYS AS (to_tsvector('simple', section || ' ' || content)) STORED,
    -- Boyut embedding modeline bağlıdır (ADR-0012: multilingual-e5-large, 1024).
    embedding     public.vector(1024) NOT NULL,
    content_hash  text        NOT NULL,
    UNIQUE (document_id, ordinal),
    FOREIGN KEY (tenant_id, document_id, collection_id)
        REFERENCES documents (tenant_id, id, collection_id) ON DELETE CASCADE
);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding public.vector_cosine_ops);
CREATE INDEX chunks_tsv_gin        ON chunks USING gin (content_tsv);
CREATE INDEX chunks_tenant_coll    ON chunks (tenant_id, collection_id);

-- Tüketici idempotency'si: bir olayın etkisi, kaydıyla aynı işlemde yazılır (ADR-0011).
CREATE TABLE processed_events (
    event_id     uuid        PRIMARY KEY,
    tenant_id    uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    processed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE documents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents        FORCE  ROW LEVEL SECURITY;
ALTER TABLE chunks           ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks           FORCE  ROW LEVEL SECURITY;
ALTER TABLE processed_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_events FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

CREATE POLICY tenant_isolation ON chunks
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

CREATE POLICY tenant_isolation ON processed_events
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- Çekirdek API indeksi okuyabilir ama yazamaz; yazma tek yerden (AI servisi) yapılır.
REVOKE INSERT, UPDATE, DELETE ON documents, chunks FROM meridian_app;
REVOKE ALL ON processed_events FROM meridian_app;

-- AI servisi: indeks tablolarına tam yetki; kaynaklarda yalnızca durum sütunlarını günceller
-- ve silinmek üzere işaretlenmiş kaynağı siler. Kimlik, üyelik, outbox tablolarını göremez.
GRANT SELECT, INSERT, UPDATE, DELETE ON documents, chunks TO meridian_ai;
GRANT SELECT, INSERT ON processed_events TO meridian_ai;
GRANT SELECT (id, tenant_id, collection_id, type, config, status) ON sources TO meridian_ai;
GRANT UPDATE (status, document_count, last_indexed_at, last_error) ON sources TO meridian_ai;
GRANT DELETE ON sources TO meridian_ai;
