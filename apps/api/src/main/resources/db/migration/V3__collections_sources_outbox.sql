-- Koleksiyonlar, kaynaklar ve transactional outbox (ADR-0004)

CREATE TABLE collections (
    id         uuid        PRIMARY KEY,
    tenant_id  uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    name       text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name),
    -- Bileşik yabancı anahtarların hedefi (aşağıdaki not).
    UNIQUE (tenant_id, id)
);

-- Yabancı anahtar denetimi RLS'i atlar: tek sütunlu bir FK, başka kiracının koleksiyon
-- kimliğini bilen birinin o koleksiyona kaynak bağlamasına izin verirdi. Bileşik FK,
-- kaynağın kiracısı ile koleksiyonun kiracısının aynı olmasını şemanın kendisinde zorlar.
CREATE TABLE sources (
    id              uuid        PRIMARY KEY,
    tenant_id       uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    collection_id   uuid        NOT NULL,
    name            text        NOT NULL,
    type            text        NOT NULL CHECK (type IN ('upload', 'web', 'github')),
    config          jsonb       NOT NULL,
    status          text        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'indexing', 'ready', 'failed', 'deleting')),
    document_count  integer     NOT NULL DEFAULT 0,
    last_indexed_at timestamptz,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, collection_id) REFERENCES collections (tenant_id, id) ON DELETE CASCADE
);

-- Cursor sayfalaması (created_at DESC, id DESC) için.
CREATE INDEX sources_page_idx ON sources (tenant_id, created_at DESC, id DESC);

ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE collections FORCE  ROW LEVEL SECURITY;
ALTER TABLE sources     ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources     FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON collections
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

CREATE POLICY tenant_isolation ON sources
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- Outbox: iş kaydıyla aynı işlemde yazılan olaylar. Aktarıcı (meridian_relay) olayları
-- RabbitMQ'ya yayımlar ve onay (publisher confirm) geldikten sonra siler. Yayın en az bir
-- kezdir; tüketiciler event_id ile tekrarı ayıklar.
CREATE TABLE outbox (
    id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id     uuid        NOT NULL UNIQUE,
    tenant_id    uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    event_type   text        NOT NULL,
    aggregate_id uuid        NOT NULL,
    payload      jsonb       NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox FORCE  ROW LEVEL SECURITY;

-- Uygulama olay yazabilir ama okuyamaz, değiştiremez, silemez: bir kiracının isteği
-- başka kiracıların olaylarını göremez ve kendi olayını yayından önce geri çekemez.
REVOKE SELECT, UPDATE, DELETE ON outbox FROM meridian_app;

CREATE POLICY app_append ON outbox FOR INSERT TO meridian_app
    WITH CHECK (tenant_id = current_tenant_id());

-- Aktarıcı tüm kiracıların olaylarını görür ama yalnızca bu tabloyu: başka tabloya yetkisi yoktur.
GRANT SELECT, DELETE ON outbox TO meridian_relay;

CREATE POLICY relay_drain ON outbox FOR SELECT TO meridian_relay USING (true);
CREATE POLICY relay_delete ON outbox FOR DELETE TO meridian_relay USING (true);
