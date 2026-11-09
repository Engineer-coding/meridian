# Runbook: İndeksleme kuyruğu birikiyor ya da DLQ'da mesaj var

Alarmlar: `IndexingDeadLetters` (DLQ'da 5 dakikadır mesaj), `IndexingBacklog` (kuyrukta 10 dakikadır 100'den fazla
mesaj), `IndexingSlow` (olayların %95'inden azı 60 saniyede bitiyor). Tasarım: [ADR-0011](../adr/0011-consumer-retry-dlq.md).

## 1. Durum
Grafana → **Meridian: genel bakış** → "Kuyruk derinliği". RabbitMQ yönetim arayüzü: http://127.0.0.1:15672.

```promql
max by (queue) (rabbitmq_detailed_queue_messages{queue=~"ai.indexing.*"})
```

## 2. DLQ'daki mesaj
DLQ'ya düşen mesaj kalıcı hatadır ya da deneme hakkını bitirmiştir; kendiliğinden boşalmaz. Kaynağın durumu
`failed` olur ve hata metni yönetim panelinde görünür.

1. Loki'de nedeni bul: `{service_name="meridian-ai"} |= "DLQ"`. Satırdaki `trace_id` ile ize geç; iz, kaynağı
   ekleyen API isteğinden başlar (outbox `traceparent`).
2. Neden giderildiyse (ör. GitHub erişimi geri geldi) kaynak yönetim panelinden **Yeniden dene** ile kuyruğa
   döner. DLQ'daki kopya incelendikten sonra RabbitMQ arayüzünden silinir; aynı olay tekrar işlenirse tüketici
   `processed_events` ile ayıklar.
3. Okunamayan mesaj (zarf bozuk, kiracı başlığı uyuşmuyor) bir saldırı ya da sürüm uyumsuzluğu olabilir:
   silmeden önce gövdesini saklayın.

## 3. Birikme
| Belirti | Olası neden | Ne yapılır |
|---|---|---|
| `ai.indexing` artıyor, işleme yok | AI servisi tüketmiyor | AI servisinin `/health/ready` ucu, RabbitMQ bağlantı logları |
| `retry.N` kuyrukları dolu | Geçici dış hata (GitHub, veritabanı) | Bekleme süreleri dolunca kendiliğinden döner; dış hizmetin durumunu doğrula |
| İşleme var ama yavaş | Embedding CPU'da | "İndeksleme p95" paneli; tüketici `PREFETCH` ve örnek sayısı |
