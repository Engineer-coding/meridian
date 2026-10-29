-- Kimlik ve kiracılık şeması (ADR-0002: paylaşımlı şema + RLS)

-- Kiracı/kullanıcı bağlamı: işlem başında set_config(..., true) ile atanır.
-- Bağlam yoksa NULL döner; NULL hiçbir satırla eşleşmez (fail-closed).
CREATE FUNCTION current_tenant_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;

CREATE FUNCTION current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE TABLE tenants (
    id         uuid        PRIMARY KEY,
    slug       text        NOT NULL UNIQUE,
    name       text        NOT NULL,
    plan       text        NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'team', 'enterprise')),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- id = OIDC 'sub' (Keycloak'ta UUID). Başka bir IdP gelirse eşleme tablosu eklenir (ADR-0005).
CREATE TABLE users (
    id           uuid        PRIMARY KEY,
    email        text        NOT NULL,
    display_name text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
    tenant_id  uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    user_id    uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role       text        NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE INDEX memberships_user_id_idx ON memberships (user_id);

ALTER TABLE tenants     ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants     FORCE  ROW LEVEL SECURITY;
ALTER TABLE users       ENABLE ROW LEVEL SECURITY;
ALTER TABLE users       FORCE  ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE  ROW LEVEL SECURITY;

-- tenants: aktif kiracı tam erişim; kullanıcı üyesi olduğu kiracıları okuyabilir (/v1/me için).
CREATE POLICY tenant_isolation ON tenants
    USING (id = current_tenant_id())
    WITH CHECK (id = current_tenant_id());

CREATE POLICY member_read ON tenants FOR SELECT
    USING (EXISTS (SELECT 1 FROM memberships m
                   WHERE m.tenant_id = tenants.id AND m.user_id = current_user_id()));

-- memberships: aktif kiracı tam erişim; kullanıcı kendi üyeliklerini okuyabilir.
CREATE POLICY tenant_isolation ON memberships
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

CREATE POLICY self_read ON memberships FOR SELECT
    USING (user_id = current_user_id());

-- users: kullanıcı kendi kaydını yönetir; aktif kiracıdaki diğer üyeleri okuyabilir.
CREATE POLICY self ON users
    USING (id = current_user_id())
    WITH CHECK (id = current_user_id());

CREATE POLICY same_tenant_read ON users FOR SELECT
    USING (EXISTS (SELECT 1 FROM memberships m
                   WHERE m.user_id = users.id AND m.tenant_id = current_tenant_id()));

-- Uygulama rolü migration geçmişine dokunamaz.
REVOKE ALL ON flyway_schema_history FROM meridian_app;