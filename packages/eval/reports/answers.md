# Retrieval değerlendirmesi — answers

- Tarih: 2026-11-02 · commit `f8a47ff-dirty`
- Model: `intfloat/multilingual-e5-large` · parça ≤ 1200 karakter, örtüşme 150
- Korpus: k8s@ef4f9c6cb538 (187 belge), kvkk@5f9e7fa79319 (1 belge) → 3093 parça
- Altın set: 23 cevaplı / 30 soru (`packages/eval/golden/v1.jsonl`, sha256 `cf0d535ee820`)

## Genel (cevaplı sorular)

| Yöntem | recall@1 | recall@3 | recall@5 | recall@10 | mrr | ndcg@5 | ndcg@10 |
|---|---|---|---|---|---|---|---|
| vector | 0.565 | 0.848 | 0.870 | 0.913 | 0.824 | 0.795 | 0.809 |
| lexical | 0.500 | 0.674 | 0.739 | 0.891 | 0.673 | 0.651 | 0.702 |
| hybrid | 0.696 | 0.804 | 0.826 | 0.913 | 0.877 | 0.815 | 0.846 |

## Kırılımlar (recall@5 / MRR)

| Grup | n | vector | lexical | hybrid |
|---|---|---|---|---|
| corpus=k8s | 14 | 0.79 / 0.71 | 0.61 / 0.56 | 0.75 / 0.80 |
| corpus=kvkk | 9 | 1.00 / 1.00 | 0.94 / 0.86 | 0.94 / 1.00 |
| lang=en | 14 | 0.79 / 0.71 | 0.61 / 0.56 | 0.75 / 0.80 |
| lang=tr | 9 | 1.00 / 1.00 | 0.94 / 0.86 | 0.94 / 1.00 |
| type=multi_hop | 8 | 0.75 / 0.85 | 0.62 / 0.57 | 0.62 / 0.81 |
| type=single_hop | 15 | 0.93 / 0.81 | 0.80 / 0.73 | 0.93 / 0.91 |

## En iyi vektör skoru (cevaplı ve cevapsız sorular)

| | ortalama | en düşük | en yüksek |
|---|---|---|---|
| answerable | 0.888 | 0.847 | 0.912 |
| unanswerable | 0.847 | 0.792 | 0.868 |

## Kaçırılan kaynaklar (hibrit, ilk 10'da yok)

- `k8s-002` sıralar [2, None] — ilk sonuç: content/en/docs/concepts/workloads/pods/probes.md § Liveness, Readiness, and Startup Probes > Probe results
- `k8s-012` sıralar [None, None] — ilk sonuç: content/en/docs/concepts/workloads/controllers/statefulset.md § StatefulSets > Pod Identity > Pod Name Label
- `k8s-014` sıralar [1, None] — ilk sonuç: content/en/docs/concepts/services-networking/network-policies.md § Network Policies > Targeting a Namespace by its name

## Kaynaklı cevap (`ollama/llama3.2:3b`, 3 kaynak)

| Ölçüt | Değer |
|---|---|
| Cevapsız soruda "bilmiyorum" (yüksek iyi) | %86 |
| Cevaplı soruda gereksiz "bilmiyorum" (düşük iyi) | %39 |
| Altın kaynak bağlamda (üst sınır) | %96 |
| Cevap en az bir kaynak gösteriyor | %100 |
| Gösterilen kaynak altın kaynak | %86 |
| Var olmayan kaynak numarası | %0 |
| Ortanca ilk token / toplam süre | 24.4 sn / 41.2 sn |

| Soru | Bilmiyorum | Kaynak | Altın kaynak gösterildi | Cevap |
|---|---|---|---|---|
| `kvkk-001` | evet | [] |  | BİLMİYORUM |
| `kvkk-002` |  | [2] | ✓ | Hayır, sağlık verisi gibi özel nitelikli kişisel veriler, kişinin açık rızası olmadan başka bir şirkete aktarılamaz [2]. Bu tür verileri akt |
| `kvkk-003` |  | [3] |  | Veri ihlalini Kurula bildirmek için otuz gün süre öngörülmüştür. Bu süre, tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde yerine  |
| `kvkk-004` |  | [1] | ✓ | Kişisel Verileri Koruma Kurulu dokuz üyeden oluşuyor ve beş üyesi Türkiye Büyük Millet Meclisi, dört üyesi Cumhurbaşkanı tarafından seçiliyo |
| `kvkk-005` | evet | [] |  | BİLMİYORUM |
| `kvkk-006` | evet | [] |  | BİLMİYORUM |
| `kvkk-007` |  | [1] | ✓ | Veri güvenliği tedbirlerini almayan bir şirkete 5.000 Türk lirasından 100.000 Türk lirasına kadar idari para cezası verilebilir. Bu informat |
| `kvkk-008` |  | [1] | ✓ | Kurulun, şikâyete cevabını vermediği tarihten itibaren altmış gün içinde başvuruya cevap verilmemesi hâlinde, ilgili kişi 60 gün içinde Kuru |
| `kvkk-009` | evet | [] |  | BİLMİYORUM |
| `kvkk-010` |  | [1, 2] | ✓ | Veri güvenliği yükümlülükleri, Veri sorumlusu'nu a) Kişisel verilerin hukuka aykırı olarak işlenmesini önlemek, b) Kişisel verilere hukuka a |
| `kvkk-011` | evet | [] |  | BİLMİYORUM |
| `kvkk-012` | evet | [] |  | BİLMİYORUM |
| `k8s-001` |  | [1, 3] | ✓ | The default type of a Kubernetes Service is `ClusterIP`, which exposes the Service on a cluster-internal IP, making it only reachable from w |
| `k8s-002` |  | [1, 2] |  | If a container's liveness probe keeps failing, the kubelet kills the container and applies its restart policy, which may lead to cascading f |
| `k8s-003` | evet | [] |  | BİLMİYORUM |
| `k8s-004` |  | [1, 2, 3] | ✓ | When creating a NodePort Service without specifying a port, Kubernetes allocates a port from the dynamic band (30086-32767) by default, as t |
| `k8s-005` | evet | [] |  | BİLMİYORUM |
| `k8s-006` |  | [1, 3] | ✓ | With default settings, up to 25% of desired Pods can be unavailable during the update process, which means that a maximum of 25% of the tota |
| `k8s-007` |  | [1, 3] | ✓ | In a brand-new Kubernetes cluster, there are four initial namespaces: `default`, `kube-node-lease`, `kube-public`, and `kube-system` [1]. Th |
| `k8s-008` |  | [1, 2] |  | By default, Secret objects are stored unencrypted in etcd, meaning they are not encrypted out of the box [1]. However, cluster administrator |
| `k8s-009` |  | [1] | ✓ | A ConfigMap is not designed to hold large chunks of data and the data stored in a ConfigMap cannot exceed 1 MiB, so there is a size limit fo |
| `k8s-010` |  | [1, 2] | ✓ | A Job will retry failing Pods up to 6 times before it is marked as failed by default, unless a backoff limit per index is specified, which w |
| `k8s-011` | evet | [] |  | BİLMİYORUM |
| `k8s-012` |  | [1, 2, 3] | ✓ | A StatefulSet requires a Headless Service to be responsible for its network identity, which must be created by the user, and this Service ca |
| `k8s-013` | evet | [] |  | BİLMİYORUM |
| `k8s-014` | evet | [] |  | BİLMİYORUM |
| `k8s-015` | evet | [] |  | BİLMİYORUM |
| `k8s-016` | evet | [] |  | BİLMİYORUM |
| `k8s-017` | evet | [] |  | BİLMİYORUM |
| `k8s-018` | evet | [] |  | BİLMİYORUM |
