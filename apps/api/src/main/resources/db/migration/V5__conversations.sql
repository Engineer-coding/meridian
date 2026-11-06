-- Konuşmalar ve mesajlar. Konuşma kişiye özeldir: RLS kiracıyla birlikte kullanıcıyı da denetler,
-- aynı kiracının başka bir üyesi (admin dahil) okuyamaz.

CREATE TABLE conversations (
    id         uuid        PRIMARY KEY,
    tenant_id  uuid        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    user_id    uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title      text,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Bileşik yabancı anahtarın hedefi (V3'teki not: FK denetimi RLS'i atlar).
    UNIQUE (tenant_id, user_id, id)
);

CREATE INDEX conversations_list_idx ON conversations (tenant_id, user_id, created_at DESC);

CREATE TABLE messages (
    id              uuid        PRIMARY KEY,
    tenant_id       uuid        NOT NULL,
    user_id         uuid        NOT NULL,
    conversation_id uuid        NOT NULL,
    role            text        NOT NULL CHECK (role IN ('user', 'assistant')),
    content         text        NOT NULL,
    -- 'interrupted': istemci akış bitmeden ayrıldı, içerik yarımdır.
    status          text        NOT NULL DEFAULT 'complete' CHECK (status IN ('complete', 'interrupted')),
    sources         jsonb       NOT NULL DEFAULT '[]',
    cited           jsonb       NOT NULL DEFAULT '[]',
    abstained       boolean     NOT NULL DEFAULT false,
    degraded        boolean     NOT NULL DEFAULT false,
    model           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, user_id, conversation_id)
        REFERENCES conversations (tenant_id, user_id, id) ON DELETE CASCADE
);

CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE  ROW LEVEL SECURITY;
ALTER TABLE messages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages      FORCE  ROW LEVEL SECURITY;

CREATE POLICY owner_only ON conversations
    USING (tenant_id = current_tenant_id() AND user_id = current_user_id())
    WITH CHECK (tenant_id = current_tenant_id() AND user_id = current_user_id());

CREATE POLICY owner_only ON messages
    USING (tenant_id = current_tenant_id() AND user_id = current_user_id())
    WITH CHECK (tenant_id = current_tenant_id() AND user_id = current_user_id());

-- Kayıt değişmez: mesajlar yalnızca eklenir.
REVOKE UPDATE ON messages FROM meridian_app;
