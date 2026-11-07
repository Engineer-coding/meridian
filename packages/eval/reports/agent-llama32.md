# Ajan ölçümü: ollama/llama3.2:3b

- Tarih: 2026-11-06 · commit `77c094e-dirty`
- 12 görev (`packages/eval/golden/agent-v1.jsonl`), bütçe 6 adım, 12000 token, 240 sn. Senaryolar sentetik ve az: sonuç yön gösterir, kesin kalite iddiası değildir.

| Ölçüt | Değer |
|---|---|
| Görev başarısı | %58 |
| Beklenen araç kullanıldı | %100 |
| "Bilmiyorum" | %42 |
| İstenmeyen ticket önerisi | 0 |
| Geçersiz çıktı | 0 |
| Ortanca adım / token / süre | 1.0 / 1920.0 / 97.65 sn |

| Görev | Tür | Başarı | Adımlar | Süre | Cevap |
|---|---|---|---|---|---|
| `search-en-pod` | search | ✓ | search_knowledge | 133.5 | A Kubernetes Pod is a group of one or more containers, with shared storage and network resources, and a specif |
| `search-en-namespace` | search |  | search_knowledge | 98.0 | BİLMİYORUM |
| `search-en-label` | search |  | search_knowledge | 134.8 | Kubernetes labels are used to describe applications in a common manner that all tools can understand, allowing |
| `search-tr-namespace` | search | ✓ | search_knowledge, search_knowledge | 127.5 | Kubernetes'te namespace, gruplar arası kaynakları tek bir cluster içinde isolated olarak isolating mechanismi  |
| `search-tr-kvkk` | search |  | search_knowledge | 145.4 | BİLMİYORUM |
| `search-tr-kvkk2` | search |  | search_knowledge | 97.3 | BİLMİYORUM |
| `sql-count` | sql | ✓ | query_sql | 41.2 | Sonuç: 2 |
| `sql-documents` | sql |  | query_sql | 35.6 | There are a total of 20 documents indexed based on the provided chunk counts. |
| `ticket-asked` | ticket | ✓ |  | 37.0 | Sunucu diski doldu |
| `ticket-asked-en` | ticket | ✓ |  | 15.7 | Login Sayfasına Hata 500 Alş |
| `abstain-weather` | abstain | ✓ | search_knowledge | 96.7 | BİLMİYORUM |
| `abstain-ceo` | abstain | ✓ | search_knowledge | 154.7 | BİLMİYORUM |
