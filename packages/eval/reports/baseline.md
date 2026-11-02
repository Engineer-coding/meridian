# Retrieval değerlendirmesi — baseline

- Tarih: 2026-11-02 · commit `32e4877`
- Model: `intfloat/multilingual-e5-large` · parça ≤ 1200 karakter, örtüşme 150
- Korpus: k8s@ef4f9c6cb538 (187 belge), kvkk@5f9e7fa79319 (1 belge) → 3093 parça
- Altın set: 23 cevaplı / 30 soru (`packages/eval/golden/v0.jsonl`, sha256 `d785ef51a1d4`)

## Genel (cevaplı sorular)

| Yöntem | recall@1 | recall@3 | recall@5 | recall@10 | mrr | ndcg@5 | ndcg@10 |
|---|---|---|---|---|---|---|---|
| vector | 0.565 | 0.826 | 0.870 | 0.913 | 0.821 | 0.793 | 0.807 |
| lexical | 0.500 | 0.674 | 0.739 | 0.848 | 0.668 | 0.651 | 0.689 |
| hybrid | 0.696 | 0.761 | 0.783 | 0.870 | 0.855 | 0.787 | 0.819 |

## Kırılımlar (recall@5 / MRR)

| Grup | n | vector | lexical | hybrid |
|---|---|---|---|---|
| corpus=k8s | 14 | 0.79 / 0.71 | 0.61 / 0.55 | 0.68 / 0.76 |
| corpus=kvkk | 9 | 1.00 / 1.00 | 0.94 / 0.86 | 0.94 / 1.00 |
| lang=en | 14 | 0.79 / 0.71 | 0.61 / 0.55 | 0.68 / 0.76 |
| lang=tr | 9 | 1.00 / 1.00 | 0.94 / 0.86 | 0.94 / 1.00 |
| type=multi_hop | 8 | 0.75 / 0.84 | 0.62 / 0.57 | 0.62 / 0.81 |
| type=single_hop | 15 | 0.93 / 0.81 | 0.80 / 0.72 | 0.87 / 0.88 |

## En iyi vektör skoru (cevaplı ve cevapsız sorular)

| | ortalama | en düşük | en yüksek |
|---|---|---|---|
| answerable | 0.888 | 0.847 | 0.912 |
| unanswerable | 0.847 | 0.792 | 0.868 |

## Kaçırılan kaynaklar (hibrit, ilk 10'da yok)

- `k8s-002` sıralar [2, None] — ilk sonuç: content/en/docs/concepts/workloads/pods/probes.md § Liveness, Readiness, and Startup Probes > Probe results
- `k8s-005` sıralar [None] — ilk sonuç: content/en/docs/concepts/cluster-administration/node-shutdown.md § Node Shutdowns > Graceful node shutdown > Pod Priority based graceful node shutdown
- `k8s-012` sıralar [None, None] — ilk sonuç: content/en/docs/concepts/workloads/controllers/statefulset.md § StatefulSets > Pod Identity > Pod Name Label
- `k8s-014` sıralar [1, None] — ilk sonuç: content/en/docs/concepts/services-networking/network-policies.md § Network Policies > Targeting a Namespace by its name
