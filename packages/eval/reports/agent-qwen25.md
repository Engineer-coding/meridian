# Ajan ölçümü: ollama/qwen2.5:3b

- Tarih: 2026-11-06 · commit `77c094e-dirty`
- 12 görev (`packages/eval/golden/agent-v1.jsonl`), bütçe 6 adım, 12000 token, 240 sn. Senaryolar sentetik ve az: sonuç yön gösterir, kesin kalite iddiası değildir.

| Ölçüt | Değer |
|---|---|
| Görev başarısı | %42 |
| Beklenen araç kullanıldı | %100 |
| "Bilmiyorum" | %33 |
| İstenmeyen ticket önerisi | 0 |
| Geçersiz çıktı | 0 |
| Ortanca adım / token / süre | 1.5 / 2786.0 / 182.25 sn |

| Görev | Tür | Başarı | Adımlar | Süre | Cevap |
|---|---|---|---|---|---|
| `search-en-pod` | search |  | search_knowledge, search_knowledge, search_knowledge, search_knowledge, search_knowledge | 236.5 | BİLMİYORUM |
| `search-en-namespace` | search | ✓ | search_knowledge, search_knowledge, search_knowledge, search_knowledge | 202.0 | Kubernetes starts with four initial namespaces: `default`, `kube-node-lease`, and `kube-system`. The fourth na |
| `search-en-label` | search |  | search_knowledge, search_knowledge, search_knowledge, search_knowledge | 199.8 | BİLMİYORUM |
| `search-tr-namespace` | search | ✓ | search_knowledge, search_knowledge, search_knowledge, search_knowledge | 239.4 | Kubernetes'te namespace, aynı küme içindeki gruplar arasında hizmetlerin isolasyonunu sağlar. Bu isolasyon, bi |
| `search-tr-kvkk` | search |  | search_knowledge, search_knowledge | 164.7 | BİLMİYORUM |
| `search-tr-kvkk2` | search |  | search_knowledge | 142.8 | BİLMİYORUM |
| `sql-count` | sql | ✓ | query_sql | 51.8 | Kayıtlarda 2 tane kaynak var. |
| `sql-documents` | sql |  | query_sql | 52.7 | There are 2 indexed documents. |
| `ticket-asked` | ticket | ✓ |  | 40.1 | Sunucu Diski Doldu |
| `ticket-asked-en` | ticket | ✓ |  | 9.3 | Login Page Error 500 |
| `abstain-weather` | abstain |  | search_knowledge, search_knowledge | 240.0 |  |
| `abstain-ceo` | abstain |  | search_knowledge | 240.0 |  |
