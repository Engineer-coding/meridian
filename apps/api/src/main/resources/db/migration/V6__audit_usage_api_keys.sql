-- Denetim kaydı, kullanım muhasebesi ve API anahtarları (ADR-0014).

-- Değiştirilemez kayıt: uygulama rolü yalnızca ekler ve okur. Kullanıcıya FK yok: kullanıcı silinse
-- de kim olduğu kimlikle kayıtta kalır. Soru metni yazılmaz: konuşmalar kişiye özeldir (T20).
CREATE TABLE audit_log (
    id            uuid        PRIMARY KEY,
    tenant_id     uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    actor_user_id uuid,
    api_key_id    uuid,
    action        text        NOT NULL,
    outcome       text        NOT NULL CHECK (outcome IN ('allowed', 'denied')),
    target_id     text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_log_page_idx ON audit_log (tenant_id, created_at DESC, id DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON audit_log
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM meridian_app;

-- Kullanım olayları da yalnızca eklenir. İçerik tutulmaz: sayılar ve model adı.
CREATE TABLE usage_events (
    id                uuid           PRIMARY KEY,
    tenant_id         uuid           NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    user_id           uuid           NOT NULL,
    model             text,
    prompt_tokens     integer        NOT NULL CHECK (prompt_tokens >= 0),
    completion_tokens integer        NOT NULL CHECK (completion_tokens >= 0),
    -- Akış kesildi ya da sağlayıcı sayaç vermedi: sayılar metin uzunluğundan tahmin edildi.
    estimated         boolean        NOT NULL DEFAULT false,
    cost_usd          numeric(12, 6) NOT NULL DEFAULT 0,
    created_at        timestamptz    NOT NULL DEFAULT now()
);

CREATE INDEX usage_events_tenant_time_idx ON usage_events (tenant_id, created_at);

ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON usage_events
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

REVOKE UPDATE, DELETE, TRUNCATE ON usage_events FROM meridian_app;

-- Gizli değer saklanmaz, yalnızca SHA-256 özeti. Arama kiracı bağlamında yapılır: anahtar ancak
-- adresindeki kiracıya aitse bulunur, RLS'i atlayan bir rol gerekmez.
CREATE TABLE api_keys (
    id           uuid        PRIMARY KEY,
    tenant_id    uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    created_by   uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name         text        NOT NULL,
    prefix       text        NOT NULL,
    key_hash     text        NOT NULL UNIQUE,
    scopes       text[]      NOT NULL CHECK (cardinality(scopes) > 0),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    last_used_at timestamptz,
    revoked_at   timestamptz
);

CREATE INDEX api_keys_tenant_idx ON api_keys (tenant_id, created_at DESC);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON api_keys
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- İptal, kaydı silmez: denetim kaydındaki anahtar kimliği anlamını korur.
REVOKE DELETE, TRUNCATE ON api_keys FROM meridian_app;
