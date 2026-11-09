-- İz bağlamı kuyruktan geçer (ADR-0017): olayı yazan isteğin W3C traceparent değeri outbox'ta saklanır,
-- aktarıcı mesaj başlığına koyar, AI servisindeki indeksleme aynı izin devamı olur. Kişisel veri değildir.
ALTER TABLE outbox ADD COLUMN traceparent text CHECK (traceparent IS NULL OR length(traceparent) <= 64);
