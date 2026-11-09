# Runbook: API hata bütçesi tükeniyor

Alarmlar: `ApiErrorBudgetBurnFast` (acil), `ApiErrorBudgetBurnSlow` (kayıt). SLO: 30 günde isteklerin %99,5'i 5xx
dönmez; sağlık uçları sayılmaz ([ADR-0018](../adr/0018-slo-alerts-dashboards.md)).

## 1. Ne kadar kötü?
Grafana → Meridian → **Meridian: genel bakış**. "Yanma hızı (1 sa)" 14,4'ün üstündeyse bütçenin %2'si bir saatte
gidiyor. "Hata oranı" panelinde 5xx çizgisine, "İstek hızı" panelinde hangi ucun etkilendiğine bakılır.

```promql
sum by (uri, status) (rate(http_server_requests_seconds_count{service_name="meridian-api", status=~"5.."}[5m]))
```

## 2. Hangi istek, neden?
Loki'de hata satırları (her satırda `trace_id` var, oradan Tempo'daki ize geçilir):

```logql
{service_name="meridian-api"} | detected_level="error"
```

İzde hangi adımın kırmızı olduğuna bakılır: veritabanı, AI servisi çağrısı (`ai /internal/v1/...`), RabbitMQ.

## 3. Sık nedenler
| Belirti | Olası neden | Ne yapılır |
|---|---|---|
| Tüm uçlarda 5xx, hazır olma DOWN | PostgreSQL'e ulaşılamıyor | `make ps`; veritabanı kapsayıcısı ve bağlantı havuzu (`HikariPool`) logları |
| Yalnızca sohbet ve ajan uçları | AI servisi kapalı | AI servisinin `/health/ready` ucu; [llm-outage.md](llm-outage.md) |
| Kaynak ekleme 5xx | RabbitMQ ya da outbox | [queue-backlog.md](queue-backlog.md) |
| Bir sürümden hemen sonra | Kod hatası | Son sürüme geri dön, sonra incele |

## 4. Kapanış
Alarm 5 dakikalık pencere sayesinde düzelince birkaç dakika içinde susar. Bütçe yarıdan fazla gittiyse olay
`docs/postmortems/` altına suçsuz bir postmortem olarak yazılır.
