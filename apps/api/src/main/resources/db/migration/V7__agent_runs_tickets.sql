-- Ajan çalıştırmaları, onaydan sonra oluşan ticket'lar ve SQL aracının görünümleri (ADR-0015).

-- Çalıştırma kişiye özeldir: amaç metni ve gözlemler konuşma kadar özeldir (T20).
CREATE TABLE agent_runs (
    id          uuid        PRIMARY KEY,
    tenant_id   uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    goal        text        NOT NULL,
    status      text        NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'waiting_approval', 'completed', 'failed',
                                              'budget_exceeded', 'interrupted')),
    steps       jsonb       NOT NULL DEFAULT '[]',
    -- Onay bekleyen ticket; onay kararı yalnızca bu kayıttaki değerleri kullanır, istemciden okumaz.
    pending     jsonb,
    answer      text,
    cited       jsonb       NOT NULL DEFAULT '[]',
    sources     jsonb       NOT NULL DEFAULT '[]',
    stop_reason text,
    model       text,
    tokens      integer     NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);

CREATE INDEX agent_runs_list_idx ON agent_runs (tenant_id, user_id, created_at DESC);
-- Kullanıcı başına tek etkin çalıştırma: yerel modelde her adım dakikalar sürebilir.
CREATE UNIQUE INDEX agent_runs_one_running ON agent_runs (tenant_id, user_id) WHERE status = 'running';

ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs FORCE  ROW LEVEL SECURITY;

CREATE POLICY owner_only ON agent_runs
    USING (tenant_id = current_tenant_id() AND user_id = current_user_id())
    WITH CHECK (tenant_id = current_tenant_id() AND user_id = current_user_id());

-- Sahte ticket sistemi: gerçek entegrasyon yok. AI servisinin bu tabloya hiçbir yetkisi yoktur.
CREATE TABLE tickets (
    id           uuid        PRIMARY KEY,
    tenant_id    uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    created_by   uuid        NOT NULL,
    agent_run_id uuid        NOT NULL,
    title        text        NOT NULL,
    description  text        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    -- Bir çalıştırmadan en fazla bir ticket; çift onay ikinci kayıt üretemez.
    UNIQUE (agent_run_id),
    FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs (tenant_id, id) ON DELETE CASCADE
);

ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON tickets
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- SQL aracının gördüğü tek şey. security_invoker: RLS çağıran rolle uygulanır; yoksa görünüm
-- sahibinin haklarıyla çalışır ve kiracı filtresi atlanırdı.
CREATE VIEW agent_sources WITH (security_invoker = true) AS
    SELECT name, type, status, document_count, last_indexed_at, created_at FROM sources;

CREATE VIEW agent_documents WITH (security_invoker = true) AS
    SELECT path, title, chunk_count, indexed_at FROM documents;

GRANT SELECT (name, document_count, last_indexed_at, created_at) ON sources TO meridian_ai;
GRANT SELECT ON agent_sources, agent_documents TO meridian_ai;
REVOKE ALL ON agent_sources, agent_documents FROM meridian_app;
