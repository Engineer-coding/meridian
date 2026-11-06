# Retrieval değerlendirmesi — answers-bge-m3

- Tarih: 2026-11-06 · commit `8abe52e`
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

## Kırılımlar (recall@5 / MRR)

| Grup | n | vector | lexical | hybrid | vector+bge-m3 | hybrid+bge-m3 |
|---|---|---|---|---|---|---|
| corpus=k8s | 83 | 0.89 / 0.71 | 0.82 / 0.71 | 0.90 / 0.80 | 0.95 / 0.84 | 0.96 / 0.84 |
| corpus=kvkk | 53 | 0.97 / 0.97 | 0.92 / 0.85 | 0.98 / 0.96 | 1.00 / 1.00 | 1.00 / 1.00 |
| lang=en | 72 | 0.91 / 0.74 | 0.82 / 0.74 | 0.90 / 0.82 | 0.96 / 0.87 | 0.96 / 0.86 |
| lang=tr | 64 | 0.93 / 0.90 | 0.90 / 0.79 | 0.97 / 0.91 | 0.98 / 0.93 | 0.99 / 0.94 |
| type=multi_hop | 33 | 0.76 / 0.72 | 0.71 / 0.70 | 0.80 / 0.79 | 0.88 / 0.82 | 0.92 / 0.85 |
| type=single_hop | 103 | 0.97 / 0.84 | 0.90 / 0.78 | 0.97 / 0.88 | 1.00 / 0.93 | 0.99 / 0.92 |

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

## Kaynaklı cevap (`ollama/llama3.2:3b`, 3 kaynak)

| Ölçüt | Değer |
|---|---|
| Cevapsız soruda "bilmiyorum" (yüksek iyi) | %90 |
| Cevaplı soruda gereksiz "bilmiyorum" (düşük iyi) | %28 |
| Altın kaynak bağlamda (üst sınır) | %96 |
| Cevap en az bir kaynak gösteriyor | %93 |
| Gösterilen kaynak altın kaynak | %88 |
| Cevap doğru (anahtar kelime, tüm cevaplı sorular) | %64 |
| Cevap doğru (model cevap verdiğinde) | %89 |
| Var olmayan kaynak numarası | %1 |
| Ortanca ilk token / toplam süre | 62.2 sn / 64.8 sn |

| Soru | Bilmiyorum | Kaynak | Altın kaynak gösterildi | Cevap |
|---|---|---|---|---|
| `kvkk-001` | evet | [] |  | BİLMİYORUM |
| `kvkk-002` |  | [3] | ✓ | Hayır, sağlık verisi gibi özel nitelikli kişisel veriler, kişinin açık rızası olmadan başka bir şirkete aktarılamaz [3]. |
| `kvkk-003` |  | [1] |  | Veri ihlalini Kurula bildirmek için 30 gün süre öngörülmüştür. Bu süre, tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde yerine ge |
| `kvkk-004` |  | [1, 2] | ✓ | Kişisel Verileri Koruma Kurulu dokuz üyeneden oluşuyor ve beş üyeyi Türkiye Büyük Millet Meclisi, dört üyesi Cumhurbaşkanı tarafından seçiyo |
| `kvkk-005` | evet | [] |  | BİLMİYORUM |
| `kvkk-006` | evet | [] |  | BİLMİYORUM |
| `kvkk-007` |  | [1] | ✓ | Veri güvenliği tedbirlerini almayan bir şirkete 5.000 Türk lirasından 100.000 Türk lirasına kadar idari para cezası verilebilir. Bu limit, K |
| `kvkk-008` |  | [2] |  | Kurul, şikâyet üzerine veya ihlal iddiasını öğrenmesi durumunda resen, görev alanına giren konularda gerekli incelemeyi yapar ve 60 gün için |
| `kvkk-009` | evet | [] |  | BİLMİYORUM |
| `kvkk-010` |  | [1, 3] | ✓ | Veri güvenliği yükümlülüklerini yerine getirmek için, Veri Sorumlusu (sistem sahipleri) personal verilerin hukuka aykırı olarak işlenmesini  |
| `kvkk-011` | evet | [] |  | BİLMİYORUM |
| `kvkk-012` | evet | [] |  | BİLMİYORUM |
| `k8s-001` |  | [1, 2] | ✓ | The default type of a Kubernetes Service is `ClusterIP`, which exposes the Service on a cluster-internal IP, making it only reachable from w |
| `k8s-002` | evet | [] |  | BİLMİYORUM |
| `k8s-003` | evet | [] |  | BİLMİYORUM |
| `k8s-004` |  | [1, 2, 3] | ✓ | When creating a NodePort Service without specifying a port, Kubernetes allocates a port from the dynamic band (30086-32767) by default, as t |
| `k8s-005` |  | [1] | ✓ | When you manually delete a Pod using `kubectl`, its containers get 30 seconds to shut down gracefully by default, as this is the default gra |
| `k8s-006` |  | [1, 3] | ✓ | With default settings, up to 25% of the desired number of Pods can be unavailable during a Deployment roll out, and up to 25% more extra Pod |
| `k8s-007` |  | [1, 2] | ✓ | In a brand-new Kubernetes cluster, there are four initial namespaces: `default`, `kube-node-lease`, `kube-public`, and `kube-system` [1]. Th |
| `k8s-008` |  | [1, 2] | ✓ | By default, Secret objects are stored unencrypted in etcd, meaning that Kubernetes Secrets are not encrypted in etcd out of the box [1]. How |
| `k8s-009` |  | [1, 2] | ✓ | Yes, there is a size limit for the data stored in a ConfigMap, which cannot exceed 1 MiB (megabyte) [1]. If you need to store settings that  |
| `k8s-010` |  | [1] | ✓ | A Job will retry failing Pods up to 6 times before it is marked as failed by default, unless a backoff limit per index is specified, which w |
| `k8s-011` | evet | [] |  | BİLMİYORUM |
| `k8s-012` |  | [1, 2] | ✓ | A StatefulSet requires a Headless Service to be responsible for its network identity, which must be created by the user themselves, and can  |
| `k8s-013` | evet | [] |  | BİLMİYORUM |
| `k8s-014` | evet | [] |  | BİLMİYORUM |
| `k8s-015` |  | [1, 2] | ✓ | If you delete a PVC whose volume was dynamically provisioned by a StorageClass that doesn't set reclaimPolicy, the PersistentVolume object w |
| `k8s-016` | evet | [] |  | BİLMİYORUM |
| `k8s-017` | evet | [] |  | BİLMİYORUM |
| `k8s-018` | evet | [] |  | BİLMİYORUM |
| `kvkk-101` |  | [] |  | Kişisel Verileri Korunması Kanunu > Altıncı Bölüm – Kişisel Verileri Koruma Kurumu ve Teşkilat > Madde 3 > (3) > Kurumun merkezi Ankara'dadı |
| `kvkk-103` |  | [] |  | Kurul toplantı yapabilmek için en az altı üyeyle toplanır ve tam sayısının salt çoğunluğuyla karar alır. |
| `kvkk-104` | evet | [] |  | BİLMİYORUM |
| `kvkk-105` |  | [1] | ✓ | Kurul kararları ve karşı oy gerekçeleri en geç on beş gün içinde yazılır. Bu information, [1] kaynakının Altıncı Bölüm – Kişisel Verileri Ko |
| `kvkk-106` | evet | [] |  | BİLMİYORUM |
| `kvkk-107` |  | [1] | ✓ | Veri sorumlusu, Kurulun inceleme konusuyla ilgili istemiş olduğu bilgi ve belgeleri on beş gün içinde göndermek zorundadır. Bu süre, Kurumun |
| `kvkk-108` |  | [1] | ✓ | Kurul verdiği giderme kararının veri sorumlusu tarafından tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde yerine getirilmesi gere |
| `kvkk-109` |  | [1] | ✓ | Veri işlemenin durdurulmasına karar verilebileceği durumlar, telafisi güç veya imkânsız zararların doğması ve açıkça hukuka aykırılık olması |
| `kvkk-110` |  | [1] | ✓ | Açık rıza, bir konuya ilişkin bilgilendirilmeye dayanan ve özgür iradeyle açıklanan rızadır [1]. Bu rızanın verilmesi, kişisel verilerin ano |
| `kvkk-111` |  | [1] | ✓ | Veri işleyen, veri sorumlusunun verdiği yetkiye dayanarak onun adına kişisel verileri işleyen gerçek veya tüzel kişidir. Bu definitione göre |
| `kvkk-112` |  | [1, 2] | ✓ | Anonim hâle getirme, kişisel verilerin cualquier surette kimliği belirli veya belirlenebilir bir gerçek kişiyle ilişkilendirilemeyecek hâle  |
| `kvkk-113` | evet | [] |  | BİLMİYORUM |
| `kvkk-114` | evet | [] |  | BİLMİYORUM |
| `kvkk-115` | evet | [] |  | BİLMİYORUM |
| `kvkk-116` |  | [1] | ✓ | İşlenebilirlik sebebi ortadan kalkan kişisel verilerin silinmesi, yok edilmesi veya anonim hâle getirilmesi gerekir [1]. |
| `kvkk-117` |  | [] |  | Yurt dışı aktarımı için yeterlilik kararını, Kurul verir ve bu karar Resmî Gazete’de yayımlanır. |
| `kvkk-118` |  | [] |  | Yeterlilik kararı, en geç dört yılda bir değerlendirilir. |
| `kvkk-119` |  | [1] | ✓ | Aidyntlatma yükümlülüğü kapsamında ilgili kişiye; veri sorumlusunun ve varsa temsilcisinin kimliği, kişisel verilerin hangi amaçla işleneceğ |
| `kvkk-120` |  | [1] | ✓ | Kanuna aykırı veri işleme yüzünden zarara uğrayan kişinin hakkı, zararın giderilmesidir. Bu hak, 11. maddede belirlenmiştir ve bu hak, perso |
| `kvkk-121` | evet | [] |  | BİLMİYORUM |
| `kvkk-122` | evet | [] |  | BİLMİYORUM |
| `kvkk-123` |  | [1] | ✓ | Başvuru için alınan ücret, veri sorumlusunun talebi reddedilmesi ya da talebin kabul edilmesi hâlinde geri ödenir. Bu durum, 13. maddeye gör |
| `kvkk-124` | evet | [] |  | BİLMİYORUM |
| `kvkk-125` |  | [1] | ✓ | Veri Sorumluları Sicili, Başkanlık tarafından kamuya açık olarak tutulur [1]. |
| `kvkk-126` | evet | [] |  | BİLMİYORUM |
| `kvkk-127` |  | [1] | ✓ | Kişisel verileri silmeyen kişi, 5237 sayılı Türk Ceza Kanununun 138 inci maddesine göre cezalandırılır. Bu, Kanunun Beşinci Bölüm'ünde yer a |
| `kvkk-128` |  | [1] | ✓ | Aydınlatma yükümlülüğünü yerine getirmeyenlere 5.000 Türk lirasından 100.000 Türk lirasına kadar idari para cezası verilir. Bu information [ |
| `kvkk-129` |  | [1] | ✓ | Kurulun verdiği idari para cezalarına karşı, idare mahkemelerinde dava açılabilir [1]. |
| `kvkk-130` |  | [1] | ✓ | Kurul üyesi olmak için en az dört yıllık lisans düzeyinde yükseköğrenim gerektiği belirtilmiştir. [1] |
| `kvkk-131` | evet | [] |  | BİLMİYORUM |
| `kvkk-132` | evet | [] |  | BİLMİYORUM |
| `kvkk-133` |  | [] |  | Kurum başkanının yokluğunda İkinci Başkan, Başkana vekalet eder. Bu information [4]'de yer almaktadır. |
| `kvkk-134` |  | [1] | ✓ | Kurumda en fazla yedi daire başkanlığı olabilir, bu sayede daire başkanlıklarının sayısı yediyi geçemez. [1] |
| `kvkk-135` |  | [3] |  | Başkan Yardımcısı atanmak için en az dört yıllık yükseköğretim kurumu mezunu, on yıl süreyle kamu hizmetinde bulunan kişiler arasından Başka |
| `kvkk-136` |  | [1] | ✓ | Kişinin kendi ailesiyle ilgili işlediği veriler, Kişisel Verilerin Korunması Kanunu'nun Yedinci Bölüm – Çeşitli Hükümler – Madde 28 – İstisn |
| `kvkk-137` |  | [1] | ✓ | Kurumun gelirleri genel bütçeden yapılacak hazine yardımları, kuruma ait taşınır ve taşınmazlardan elde edilen gelirler, alınan bağış ve yar |
| `kvkk-151` |  | [1, 2] | ✓ | Veri Sorumluları Siciline kaydolmayan bir şirket, veri işlemeye başlamadan önce kaydolmalıdır. Bu durum, Kurulca belirlenecek objektif krite |
| `kvkk-152` | evet | [] |  | BİLMİYORUM |
| `kvkk-153` | evet | [] |  | BİLMİYORUM |
| `kvkk-154` |  | [1] | ✓ | Veri sorumlusu başvuruya 30 gün içinde cevap vermezse, ilgili kişi, bu sürenin geçmesi üzerine, başvuruyu Kurula şikâyette bulunabilir ve bu |
| `kvkk-155` |  | [1, 2] | ✓ | Silinmesi gereken kişisel verileri silmemenin dayanağı, 7 nci maddede öngörülen şartlar çerçevesinde kişisel verilerin silinmesini veya yok  |
| `kvkk-156` |  | [] |  | Kişisel Verileri Korunması Kanunu > Altıncı Bölüm – Kişisel Verileri Koruma Kurumu ve Teşkilat > Madde 21 – Kişisel Verileri Koruma Kurulu i |
| `kvkk-157` | evet | [] |  | BİLMİYORUM |
| `kvkk-158` |  | [3] | ✓ | Veri güvenliği yükümlülüklerini Kurul belirler. Veri sorumlusu, ihlalde bulunursa, veri sorumlusu sorumlu değildir. Bu görev, Kurumun yetkis |
| `kvkk-171` | evet | [] |  | BİLMİYORUM |
| `kvkk-172` | evet | [] |  | BİLMİYORUM |
| `kvkk-173` | evet | [] |  | BİLMİYORUM |
| `kvkk-174` | evet | [] |  | BİLMİYORUM |
| `kvkk-175` | evet | [] |  | BİLMİYORUM |
| `kvkk-176` | evet | [] |  | BİLMİYORUM |
| `kvkk-177` |  | [1] |  | Veri ihlali bildirim formunda, Veri Sorumlusu ve varsa temsilcisinin kimlik ve adres bilgileri [1], kişisel verilerin hangi amaçla işleneceğ |
| `kvkk-178` | evet | [] |  | BİLMİYORUM |
| `k8s-101` | evet | [] |  | BİLMİYORUM |
| `k8s-102` |  | [1, 2] | ✓ | The HorizontalPodAutoscaler controller considers a Pod "not yet ready" if it's unready and transitioned to ready within a short, configurabl |
| `k8s-103` |  | [1, 2] | ✓ | The default value for the `--horizontal-pod-autoscaler-cpu-initialization-period` option is 5 minutes [1]. This means that during this time  |
| `k8s-104` |  | [1, 2, 3] | ✓ | The VPA Recommender calculates three types of recommendations: target recommendation (optimal resources for typical usage), lower bound (min |
| `k8s-105` |  | [1, 2, 3] | ✓ | A VerticalPodAutoscaler stores its recommendations in the `.status.recommendation` field of its resource, which includes target recommendati |
| `k8s-106` |  | [1, 2] | ✓ | The group-template hierarchy supports a maximum depth of 4 levels, which means that there can be up to 3 levels of nesting before reaching t |
| `k8s-107` |  | [1, 2, 3] | ✓ | The `CompositePodGroup` resource belongs to the `scheduling.k8s.io/v1alpha3` API group, which must be enabled for its use, as well as the `C |
| `k8s-108` |  | [1] | ✓ | A device plugin signals that it does not have a NUMA affinity preference for a given device by returning a nil TopologyInfo, indicating that |
| `k8s-109` |  | [1, 2] | ✓ | A Deployment's `.spec.selector` cannot be changed after creation in `apps/v1`, as it is immutable once created, and any attempt to update it |
| `k8s-110` | evet | [] |  | BİLMİYORUM |
| `k8s-111` |  | [1, 2] | ✓ | You should use a DaemonSet when it is important that a copy of a Pod always run on all or certain hosts, as this provides node-level functio |
| `k8s-112` |  | [1] | ✓ | The total number of individual attribute values per device (scalar fields plus all list elements combined) is limited to 48 [1]. When any de |
| `k8s-113` |  | [1, 2] | ✓ | Allocating a device with admin access is not exempt from device taints, as an admin must explicitly tolerate all taints to access tainted de |
| `k8s-114` |  | [1] | ✓ | Node-local DRA drivers should use the **associated-node:<verb>** prefix when updating `resourceclaims/driver`, as specified in the Hardening |
| `k8s-115` |  | [1, 2] | ✓ | Only one queueSort plugin can be enabled at a time, as specified by the Hardening Guide for custom schedulers [1]. This means that if you tr |
| `k8s-116` | evet | [] |  | BİLMİYORUM |
| `k8s-117` |  | [1, 2] | ✓ | If a Pod references a PodGroup that does not exist yet, the Pod remains pending until the entire group hierarchy exists in the cluster [1].  |
| `k8s-118` |  | [1, 2] | ✓ | Controllers must create objects in this order: first `Workload` (the scheduling policy template), then `PodGroup` (the runtime instance) whi |
| `k8s-119` |  | [1, 2, 3] | ✓ | To disable Memory QoS, set the `MemoryQoS` feature gate to `false`, ensure that `memoryReservationPolicy` is unset or set to `None`, and res |
| `k8s-120` |  | [1] | ✓ | Incorrect implementation of liveness probes can lead to cascading failures, resulting in restarting a container under high load [1]. This ca |
| `k8s-121` |  | [1, 2] | ✓ | A Pod with `setHostnameAsFQDN` enabled and an FQDN longer than 64 characters will remain in the `Pending` status (`ContainerCreating`) as se |
| `k8s-122` |  | [1] | ✓ | If a container has no CPU and memory limits, the downward API exposes the maximum allocatable value for CPU and memory based on the node all |
| `k8s-123` | evet | [] |  | BİLMİYORUM |
| `k8s-125` |  | [1] | ✓ | When a request violates a LimitRange constraint, the API server returns an HTTP status code `403 Forbidden` [1]. This message explains the s |
| `k8s-126` |  | [1, 2] | ✓ | If a node's container runtime does not support the `v1` CRI API on Kubernetes 1.26 or later, the kubelet will not register the node because  |
| `k8s-127` |  | [1] | ✓ | A Windows Pod can have only 1 DNS suffix, which is the DNS suffix associated with that Pod's namespace (example: `mydns.svc.cluster.local`)  |
| `k8s-129` |  | [1] | ✓ | DNS and route settings for Windows containers are not stored as files inside `/etc`, but rather must be configured using Windows APIs run in |
| `k8s-131` |  | [1, 2, 3] | ✓ | The minimum Linux kernel version required for cgroup v2 is 5.8 or later, as stated in source [1]. However, a kernel version of 4.20 or later |
| `k8s-132` |  | [1, 2] | ✓ | A VolumeAttributesClass can define at most 512 parameters, as stated in both Volume Attributes Classes > Parameters and Storage Classes > Pa |
| `k8s-133` |  | [1, 2] | ✓ | If you notice stuck evictions where the Eviction API only returns 429 or 500 responses, try aborting or pausing the automated operation caus |
| `k8s-134` |  | [1, 2, 3] | ✓ | The `ownerReferences.blockOwnerDeletion` field controls whether specific dependents block garbage collection from deleting their owner objec |
| `k8s-135` |  | [1] | ✓ | Kubernetes provides two main API kinds that can be used to store configuration: ConfigMap and Secret [1]. These APIs are designed to allow c |
| `k8s-136` |  | [2, 3] | ✓ | Cluster Autoscaler adds Nodes to pre-configured Node groups that best fit the requests of pending Pods during provisioning [2]. When consoli |
| `k8s-137` |  | [1, 2] | ✓ | When set to `Local`, Kubernetes tells kube-proxy to use node local endpoints for cluster internal traffic, effectively filtering out non-nod |
| `k8s-138` | evet | [] |  | BİLMİYORUM |
| `k8s-139` |  | [1, 2, 3] | ✓ | You can specify the RuntimeClass for a Pod to ensure that Kubernetes runs those containers using a particular container runtime, allowing yo |
| `k8s-140` |  | [1, 2, 3] | ✓ | The first steps toward custom Topology Aware Routing heuristics were included in Kubernetes version 1.27, which is mentioned as a release th |
| `k8s-142` |  | [1] | ✓ | The `ExtendedResourceToleration` admission controller automatically adds the correct toleration to a pod when it requests an extended resour |
| `k8s-145` |  | [1, 2] | ✓ | Gateway API has four stable API kinds: GatewayClass, Gateway, HTTPRoute, and GRPCRoute [1]. These kinds are organized into different API kin |
| `k8s-146` |  | [1] | ✓ | When authentication fails, the API server returns HTTP status code 401 [1]. This is stated as "If the request cannot be authenticated, it is |
| `k8s-148` |  | [1, 2] | ✓ | The `kubernetes.io/pv-protection` finalizer prevents accidental deletion of `PersistentVolume` objects that are still in use by a Pod, allow |
| `k8s-149` | evet | [] |  | BİLMİYORUM |
| `k8s-150` |  | [1, 2, 3] | ✓ | The maximum length of list items in `compositePodGroupTemplates` and `podGroupTemplates` is strictly capped at a maximum of 8 items, as stat |
| `k8s-151` |  | [1, 2] | ✓ | In-tree controllers set `DisableDeclarativeValidation` to avoid checking the same fields twice during validation, as the API server already  |
| `k8s-161` |  | [] |  | Bir Pod kaynak isteği LimitRange'i ihlal ederse API sunucusu 403 Forbidden durum kodunu döner. Bu durum, LimitRange tarafından ihlalcin bein |
| `k8s-162` |  | [2] | ✓ | Cgroup v2 için en düşük Linux çekirdek sürümü 5.8'dir. [2] kaynağının "cgroup v2 > Using cgroup v2 > Requirements" bölümünde bu information  |
| `k8s-163` |  | [1] | ✓ | Windows üzerinde çalışan bir Pod, tek bir DNS sonekine sahip olabilir. Bu sonek, Pod'un namespace'ine bağlı olarak belirlenir ve Windows, bu |
| `k8s-164` | evet | [] |  | BİLMİYORUM |
| `k8s-165` |  | [1] | ✓ | Kimlik doğrulama başarısız olursa API sunucusu 401 HTTP kodunu döner. Bu kod, kimlik doğrulama başarısıznessini gösterir ve API sunucusu, ku |
| `k8s-166` |  | [1] | ✓ | VolumeAttributesClass, en fazla 512 parameter tanımı yapabilir. Bu limit, her parameterın toplam uzunluğu da dahil olmak üzere total length  |
| `k8s-167` |  | [1] |  | Bir Pod'un başvurduğu PodGroup henüz yoksa, o Pod pending olarak kalır. [1] PodGroup'ün referanslandığı bir PodGroup belum oluşturulmuştur v |
| `k8s-168` | evet | [] |  | BİLMİYORUM |
| `k8s-171` |  | [1, 2] | ✓ | The group-template hierarchy supports a maximum depth of 4 levels [1] and is strictly capped at a maximum of 8 items in lists such as `compo |
| `k8s-172` | evet | [] |  | BİLMİYORUM |
| `k8s-173` |  | [1, 3] | ✓ | On Windows nodes, Pod-to-pod communication is restricted due to the lack of FQDN resolution support and limited DNS suffixes, which can lead |
| `k8s-174` |  | [1, 3] | ✓ | A `Workload` must exist before a PodGroup can use a `podGroupTemplateRef`, as the API server rejects the PodGroup creation request if the re |
| `k8s-175` | evet | [] |  | BİLMİYORUM |
| `k8s-176` | evet | [] |  | BİLMİYORUM |
| `k8s-177` |  | [2, 3] |  | The Resource manager uses the Topology Manager's data to make resource assignment decisions [2]. A device plugin sends its `TopologyInfo` st |
| `k8s-178` |  | [2] |  | A workload should be a DaemonSet when it's essential to run a node-level service that provides facilities local to a specific node, such as  |
| `k8s-179` | evet | [] |  | BİLMİYORUM |
| `k8s-180` |  | [2, 3] | ✓ | The kubelet requires that the container runtime supports the `v1` CRI API for cgroup v2 to work since 1.26 [2], and it needs the runtime to  |
| `k8s-181` |  | [1, 2, 3] | ✓ | The four stable Gateway API kinds are GatewayClass, Gateway, HTTPRoute, and GRPCRoute [1]. The internal traffic policy Local considers only  |
| `k8s-182` | evet | [] |  | BİLMİYORUM |
| `k8s-183` |  | [1, 3] | ✓ | The total number of individual attribute values per device is limited to 48, including scalar fields and list elements combined [3]. An admi |
| `k8s-184` | evet | [] |  | BİLMİYORUM |
| `k8s-185` |  | [1, 3] | ✓ | Bir Service'in iç trafik politikası Local olduğunda, kube-proxy only node local endpoints'i kullanır (Kaynak: [1]). Varsayılan değer Cluster |
| `k8s-186` | evet | [] |  | BİLMİYORUM |
| `k8s-187` | evet | [] |  | BİLMİYORUM |
| `k8s-191` | evet | [] |  | BİLMİYORUM |
| `k8s-192` | evet | [] |  | BİLMİYORUM |
| `k8s-193` | evet | [] |  | BİLMİYORUM |
| `k8s-194` | evet | [] |  | BİLMİYORUM |
| `k8s-195` | evet | [] |  | BİLMİYORUM |
| `k8s-196` | evet | [] |  | BİLMİYORUM |
| `k8s-197` | evet | [] |  | BİLMİYORUM |
| `k8s-198` | evet | [] |  | BİLMİYORUM |
| `k8s-199` | evet | [] |  | BİLMİYORUM |
| `k8s-200` | evet | [] |  | BİLMİYORUM |
| `k8s-201` |  | [1] |  | Kubernetes'te bir Secret'ı döndürmek (rotation) için önerilen süre 15 dakika (yani 0,25 saat)dir. Bu süre, Kubernetes v1.22 ve daha yeni sür |
| `k8s-202` | evet | [] |  | BİLMİYORUM |
| `k8s-203` | evet | [] |  | BİLMİYORUM |
| `k8s-204` | evet | [] |  | BİLMİYORUM |
