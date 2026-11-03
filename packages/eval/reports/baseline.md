# Retrieval değerlendirmesi — baseline

- Tarih: 2026-11-03 · commit `0be4012-dirty`
- Model: `intfloat/multilingual-e5-large` · parça ≤ 1200 karakter, örtüşme 150
- Korpus: k8s@ef4f9c6cb538 (187 belge), kvkk@5f9e7fa79319 (1 belge) → 3093 parça
- Altın set: 23 cevaplı / 30 soru (`packages/eval/golden/v1.jsonl`, sha256 `cf0d535ee820`)

## Genel (cevaplı sorular)

| Yöntem | recall@1 | recall@3 | recall@5 | recall@10 | mrr | ndcg@5 | ndcg@10 | yeniden sıralama (sn/soru) |
|---|---|---|---|---|---|---|---|---|
| vector | 0.565 | 0.848 | 0.870 | 0.913 | 0.824 | 0.795 | 0.809 | 0.0 |
| lexical | 0.500 | 0.674 | 0.739 | 0.891 | 0.673 | 0.651 | 0.702 | 0.0 |
| hybrid | 0.696 | 0.804 | 0.826 | 0.913 | 0.877 | 0.815 | 0.846 | 0.0 |
| vector+bge-m3 | 0.609 | 0.848 | 0.913 | 0.935 | 0.824 | 0.826 | 0.834 | 14.0 |
| hybrid+bge-m3 | 0.609 | 0.848 | 0.891 | 0.957 | 0.821 | 0.819 | 0.842 | 13.9 |
| vector+jina-v2 | 0.674 | 0.804 | 0.848 | 0.935 | 0.861 | 0.815 | 0.847 | 10.4 |
| hybrid+jina-v2 | 0.652 | 0.804 | 0.848 | 0.935 | 0.839 | 0.805 | 0.836 | 10.7 |

## Kırılımlar (recall@5 / MRR)

| Grup | n | vector | lexical | hybrid | vector+bge-m3 | hybrid+bge-m3 | vector+jina-v2 | hybrid+jina-v2 |
|---|---|---|---|---|---|---|---|---|
| corpus=k8s | 14 | 0.79 / 0.71 | 0.61 / 0.56 | 0.75 / 0.80 | 0.86 / 0.71 | 0.82 / 0.71 | 0.79 / 0.81 | 0.79 / 0.81 |
| corpus=kvkk | 9 | 1.00 / 1.00 | 0.94 / 0.86 | 0.94 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 0.94 / 0.94 | 0.94 / 0.89 |
| lang=en | 14 | 0.79 / 0.71 | 0.61 / 0.56 | 0.75 / 0.80 | 0.86 / 0.71 | 0.82 / 0.71 | 0.79 / 0.81 | 0.79 / 0.81 |
| lang=tr | 9 | 1.00 / 1.00 | 0.94 / 0.86 | 0.94 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 0.94 / 0.94 | 0.94 / 0.89 |
| type=multi_hop | 8 | 0.75 / 0.85 | 0.62 / 0.57 | 0.62 / 0.81 | 0.75 / 0.72 | 0.81 / 0.72 | 0.69 / 0.78 | 0.69 / 0.71 |
| type=single_hop | 15 | 0.93 / 0.81 | 0.80 / 0.73 | 0.93 / 0.91 | 1.00 / 0.88 | 0.93 / 0.88 | 0.93 / 0.91 | 0.93 / 0.91 |

## En iyi vektör skoru (cevaplı ve cevapsız sorular)

| | ortalama | en düşük | en yüksek |
|---|---|---|---|
| answerable | 0.888 | 0.847 | 0.912 |
| unanswerable | 0.847 | 0.792 | 0.868 |

## Kaçırılan kaynaklar (hibrit, ilk 10'da yok)

- `k8s-002` sıralar [2, None] — ilk sonuç: content/en/docs/concepts/workloads/pods/probes.md § Liveness, Readiness, and Startup Probes > Probe results
- `k8s-012` sıralar [None, None] — ilk sonuç: content/en/docs/concepts/workloads/controllers/statefulset.md § StatefulSets > Pod Identity > Pod Name Label
- `k8s-014` sıralar [1, None] — ilk sonuç: content/en/docs/concepts/services-networking/network-policies.md § Network Policies > Targeting a Namespace by its name
