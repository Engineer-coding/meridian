-- Idempotency-Key kayıtları: anahtar kullanıcı başına benzersizdir.
-- users tablosuna yabancı anahtar bilerek yok: anahtar, kullanıcı kaydıyla aynı işlemde
-- ve ondan önce talep edilir. Süresi dolan kayıtlar temizlik işiyle silinir (24 saat).
CREATE TABLE idempotency_keys (
    user_id      uuid        NOT NULL,
    key          text        NOT NULL,
    request_hash text        NOT NULL,
    resource_id  uuid,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, key)
);

CREATE INDEX idempotency_keys_created_at_idx ON idempotency_keys (created_at);

ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_keys FORCE  ROW LEVEL SECURITY;

CREATE POLICY owner_only ON idempotency_keys
    USING (user_id = current_user_id())
    WITH CHECK (user_id = current_user_id());
