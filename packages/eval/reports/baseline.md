# Retrieval değerlendirmesi — baseline

- Tarih: 2026-11-07 · commit `e66c6b9-dirty`
- Model: `intfloat/multilingual-e5-large` · parça ≤ 1200 karakter, örtüşme 150
- Korpus: k8s@ef4f9c6cb538 (187 belge), kvkk@5f9e7fa79319 (1 belge) → 3093 parça
- Altın set: 136 cevaplı / 165 soru (`packages/eval/golden/v2.jsonl`, sha256 `84ad10ae48b0`)

## Genel (cevaplı sorular)

| Yöntem | recall@1 | recall@3 | recall@5 | recall@10 | mrr | ndcg@5 | ndcg@10 | yeniden sıralama (sn/soru) |
|---|---|---|---|---|---|---|---|---|
| vector | 0.643 | 0.897 | 0.919 | 0.963 | 0.816 | 0.828 | 0.845 | 0.0 |
| lexical | 0.614 | 0.783 | 0.857 | 0.912 | 0.762 | 0.766 | 0.785 | 0.0 |
| hybrid | 0.706 | 0.886 | 0.930 | 0.967 | 0.862 | 0.860 | 0.874 | 0.0 |
| vector+bge-m3 | 0.765 | 0.938 | 0.971 | 0.974 | 0.902 | 0.911 | 0.913 | 15.0 |
| hybrid+bge-m3 | 0.754 | 0.949 | 0.974 | 0.989 | 0.901 | 0.911 | 0.916 | 15.8 |
| vector+jina-v2 | 0.739 | 0.904 | 0.926 | 0.971 | 0.877 | 0.875 | 0.892 | 13.4 |
| hybrid+jina-v2 | 0.732 | 0.912 | 0.934 | 0.978 | 0.879 | 0.878 | 0.895 | 13.2 |

## Kırılımlar (recall@5 / MRR)

| Grup | n | vector | lexical | hybrid | vector+bge-m3 | hybrid+bge-m3 | vector+jina-v2 | hybrid+jina-v2 |
|---|---|---|---|---|---|---|---|---|
| corpus=k8s | 83 | 0.89 / 0.71 | 0.82 / 0.71 | 0.90 / 0.80 | 0.95 / 0.84 | 0.96 / 0.84 | 0.89 / 0.81 | 0.90 / 0.82 |
| corpus=kvkk | 53 | 0.97 / 0.97 | 0.92 / 0.85 | 0.98 / 0.96 | 1.00 / 1.00 | 1.00 / 1.00 | 0.99 / 0.98 | 0.99 / 0.97 |
| lang=en | 72 | 0.91 / 0.74 | 0.82 / 0.74 | 0.90 / 0.82 | 0.96 / 0.87 | 0.96 / 0.86 | 0.89 / 0.84 | 0.90 / 0.84 |
| lang=tr | 64 | 0.93 / 0.90 | 0.90 / 0.79 | 0.97 / 0.91 | 0.98 / 0.93 | 0.99 / 0.94 | 0.97 / 0.92 | 0.98 / 0.93 |
| type=multi_hop | 33 | 0.76 / 0.72 | 0.71 / 0.70 | 0.80 / 0.79 | 0.88 / 0.82 | 0.92 / 0.85 | 0.73 / 0.73 | 0.76 / 0.75 |
| type=single_hop | 103 | 0.97 / 0.84 | 0.90 / 0.78 | 0.97 / 0.88 | 1.00 / 0.93 | 0.99 / 0.92 | 0.99 / 0.93 | 0.99 / 0.92 |

## En iyi vektör skoru (cevaplı ve cevapsız sorular)

| | ortalama | en düşük | en yüksek |
|---|---|---|---|
| answerable | 0.872 | 0.801 | 0.923 |
| unanswerable | 0.844 | 0.792 | 0.882 |

## Kaçırılan kaynaklar (hibrit, ilk 10'da yok)

- `k8s-002` sıralar [2, None] — ilk sonuç: content/en/docs/concepts/workloads/pods/probes.md § Liveness, Readiness, and Startup Probes > Probe results
- `k8s-012` sıralar [None, None] — ilk sonuç: content/en/docs/concepts/workloads/controllers/statefulset.md § StatefulSets > Pod Identity > Pod Name Label
- `k8s-014` sıralar [1, None] — ilk sonuç: content/en/docs/concepts/services-networking/network-policies.md § Network Policies > Targeting a Namespace by its name
- `kvkk-158` sıralar [None, 1] — ilk sonuç: kvkk/6698.md § Kişisel Verilerin Korunması Kanunu > Üçüncü Bölüm – Haklar ve Yükümlülükler > Madde 12 – Veri güvenliğine ilişkin yükümlülükler
- `k8s-116` sıralar [None] — ilk sonuç: content/en/docs/concepts/workloads/workload-api/policies.md § PodGroup Scheduling Policies
- `k8s-173` sıralar [1, None] — ilk sonuç: content/en/docs/concepts/services-networking/dns-pod-service.md § DNS for Services and Pods > DNS resolution on Windows nodes
- `k8s-186` sıralar [None, 2] — ilk sonuç: content/en/docs/concepts/policy/limit-range.md § Limit Ranges > LimitRange and admission checks for Pods
