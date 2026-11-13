# Retrieval değerlendirmesi — answers

- Tarih: 2026-11-13 · commit `5c48dd9-dirty`
- Model: `intfloat/multilingual-e5-large` · parça ≤ 1200 karakter, örtüşme 150
- Korpus: k8s@ef4f9c6cb538 (187 belge), kvkk@5f9e7fa79319 (1 belge) → 3093 parça
- Altın set: 136 cevaplı / 165 soru (`packages/eval/golden/v2.jsonl`, sha256 `84ad10ae48b0`)

## Genel (cevaplı sorular)

| Yöntem | recall@1 | recall@3 | recall@5 | recall@10 | mrr | ndcg@5 | ndcg@10 | yeniden sıralama (sn/soru) |
|---|---|---|---|---|---|---|---|---|
| vector | 0.643 | 0.897 | 0.919 | 0.963 | 0.816 | 0.828 | 0.845 | 0.0 |
| lexical | 0.614 | 0.783 | 0.857 | 0.912 | 0.762 | 0.766 | 0.785 | 0.0 |
| hybrid | 0.706 | 0.886 | 0.930 | 0.967 | 0.862 | 0.860 | 0.874 | 0.0 |

## Kırılımlar (recall@5 / MRR)

| Grup | n | vector | lexical | hybrid |
|---|---|---|---|---|
| corpus=k8s | 83 | 0.89 / 0.71 | 0.82 / 0.71 | 0.90 / 0.80 |
| corpus=kvkk | 53 | 0.97 / 0.97 | 0.92 / 0.85 | 0.98 / 0.96 |
| lang=en | 72 | 0.91 / 0.74 | 0.82 / 0.74 | 0.90 / 0.82 |
| lang=tr | 64 | 0.93 / 0.90 | 0.90 / 0.79 | 0.97 / 0.91 |
| type=multi_hop | 33 | 0.76 / 0.72 | 0.71 / 0.70 | 0.80 / 0.79 |
| type=single_hop | 103 | 0.97 / 0.84 | 0.90 / 0.78 | 0.97 / 0.88 |

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
| Cevapsız soruda "bilmiyorum" (yüksek iyi) | %93 |
| Cevaplı soruda gereksiz "bilmiyorum" (düşük iyi) | %30 |
| Altın kaynak bağlamda (üst sınır) | %93 |
| Cevap en az bir kaynak gösteriyor | %93 |
| Gösterilen kaynak altın kaynak | %80 |
| Cevap doğru (anahtar kelime, tüm cevaplı sorular) | %61 |
| Cevap doğru (model cevap verdiğinde) | %87 |
| Var olmayan kaynak numarası | %1 |
| Ortanca ilk token / toplam süre | 58.2 sn / 65.7 sn |

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
| `kvkk-101` | evet | [] |  | BİLMİYORUM |
| `kvkk-103` |  | [] |  | Kurul toplantı yapabilmek için en az altı üyeyle toplanır ve üye tam sayısının salt çoğunluğuyla karar alır. |
| `kvkk-104` | evet | [] |  | BİLMİYORUM |
| `kvkk-105` | evet | [] |  | BİLMİYORUM |
| `kvkk-106` | evet | [] |  | BİLMİYORUM |
| `kvkk-107` |  | [1] | ✓ | Veri sorumlusu, Kurulun inceleme konusuyla ilgili istemiş olduğu bilgi ve belgeleri on beş gün içinde göndermek zorundadır. Bu süre, incelem |
| `kvkk-108` |  | [] |  | Kurul verdiği giderme kararının veri sorumlusu tarafından tebliğden itibaren otuz gün içinde yerine getirilmesi gerekir. |
| `kvkk-109` |  | [] |  | Veri işlemenin durdurulmasına karar verilebilir, telafisi güç veya imkânsız zararların doğması ve açıkça hukuka aykırılık olması hâlinde. (7 |
| `kvkk-110` |  | [1] | ✓ | Açık rıza, bir konuya ilişkin bilgilendirilmeye dayanan ve özgür iradeyle açıklanan rızadır [1]. |
| `kvkk-111` |  | [1] | ✓ | Veri işleyen, veri sorumlusunun verdiği yetkiye dayanarak onun adına kişisel verileri işleyen gerçek veya tüzel kişidir. Bu, veri sorumlusu  |
| `kvkk-112` |  | [1, 2] | ✓ | Anonim hâle getirme, kişisel verilerin kimliği belirli veya belirlenebilir bir gerçek kişiyle ilişkilendirilemeyecek hâle getirilmesini ifad |
| `kvkk-113` | evet | [] |  | BİLMİYORUM |
| `kvkk-114` | evet | [] |  | BİLMİYORUM |
| `kvkk-115` | evet | [] |  | BİLMİYORUM |
| `kvkk-116` |  | [1] | ✓ | İşlenebilirlik sebebi ortadan kalkan kişisel verilerin silinmesi, yok edilmesi veya anonim hâle getirilmesi gerekir [1]. |
| `kvkk-117` |  | [] |  | Yurt dışı aktarımı için yeterlilik kararını, Kurul verir ve bu karar Resmî Gazete’de yayımlanır. |
| `kvkk-118` |  | [] |  | Yeterlilik kararı, en geç dört yılda bir değerlendirilir. |
| `kvkk-119` |  | [1] | ✓ | Aidyntatma yükümlülüğü kapsamında ilgili kişiye; veri sorumlusunun ve varsa temsilcisinin kimliği, kişisel verilerin hangi amaçla işleneceği |
| `kvkk-120` | evet | [] |  | BİLMİYORUM |
| `kvkk-121` |  | [3] |  | Veri sorumlusu, kendi kurumunda kanuna uymayı sağlamak için gerekli denetimleri yapmak veya yaptırmak zorundadır [3]. |
| `kvkk-122` | evet | [] |  | BİLMİYORUM |
| `kvkk-123` |  | [1] | ✓ | Başvuru için alınan ücret, veri sorumlusunun talebi reddettiği veya hatası nedeniyle alınır. Bu durumda, alınan ücret ilgili kişiye iade edi |
| `kvkk-124` |  | [3] |  | Kişilik hakları ihlal edilen kişinin tazminat hakkı şikâyet yolu nedeniyle ortadan kalkmaz, ancak genel hükümlere göre tazminat hakkı saklı  |
| `kvkk-125` |  | [1] | ✓ | Veri Sorumluları Sicilini, Başkanlık tarafından kamuya açık olarak tutulur [1]. |
| `kvkk-126` | evet | [] |  | BİLMİYORUM |
| `kvkk-127` |  | [1] | ✓ | Cezalandırılan kişi, 5237 sayılı Türk Ceza Kanununun 138 inci maddesine göre cezalandırılır. Bu, kişisel verileri silmeyen veya anonim hâle  |
| `kvkk-128` |  | [1] | ✓ | Aydınlatma yükümlülüğünü yerine getirmeyenlere 5.000 Türk lirasından 100.000 Türk lirasına kadar idari para cezası verilir. Bu information [ |
| `kvkk-129` |  | [1] | ✓ | Kurulun verdiği idari para cezalarına karşı, idare mahkemelerinde dava açılabilir. Bu information [1] kaynakından alınmıştır. |
| `kvkk-130` |  | [1] | ✓ | Kurul üyesi olmak için en az dört yıllık lisans düzeyinde yükseköğrenim gerektiği belirtilmiştir. [1] |
| `kvkk-131` | evet | [] |  | BİLMİYORUM |
| `kvkk-132` | evet | [] |  | BİLMİYORUM |
| `kvkk-133` |  | [] |  | Kurum başkanının yokluğunda ona vekalet eden İkinci Başkan'dır. [4] |
| `kvkk-134` |  | [1] | ✓ | Kurumda en fazla yedi daire başkanlığı olabilir. Bu, dördüncü fıkrada sayılan görevleri daire başkanlıklarına olarak mentioned being done [1 |
| `kvkk-135` |  | [3] |  | Başkan Yardımcısı atanmak için en az dört yıllık yükseköğretim kurumu mezunu, on yıl süreyle kamu hizmetinde bulunan kişiler arasından atanı |
| `kvkk-136` |  | [1] | ✓ | Kişinin kendi ailesiyle ilgili işlediği veriler, Kişisel Verilerin Korunması Kanunu'nun Yedinci Bölüm – Çeşitli Hükümler – Madde 28 – İstisn |
| `kvkk-137` |  | [1] | ✓ | Kurumun gelirleri genel bütçeden yapılacak hazine yardımları, kuruma ait taşınır ve taşınmazlardan elde edilen gelirler, alınan bağış ve yar |
| `kvkk-151` | evet | [] |  | BİLMİYORUM |
| `kvkk-152` | evet | [] |  | BİLMİYORUM |
| `kvkk-153` | evet | [] |  | BİLMİYORUM |
| `kvkk-154` | evet | [] |  | BİLMİYORUM |
| `kvkk-155` |  | [1] | ✓ | Silinmesi gereken kişisel verileri silmemenin dayanağı, 26/9/2004 tarihli ve 5237 sayılı Türk Ceza Kanununun 135 ila 140 ıncı madde hükümler |
| `kvkk-156` | evet | [] |  | BİLMİYORUM |
| `kvkk-157` |  | [3] |  | Özel nitelikli verileri işlerken alınması gereken önlemleri, Veri sorumlusu belirler [3]. Bu kanunun "Veri güvenliğine ilişkin yükümlülükler |
| `kvkk-158` |  | [1] | ✓ | Veri güvenliği yükümlülüklerini, Veri Sorumlusu belirler. Veri Sorumlusu, kendi kurum veya kuruluşunda bu Kanun hükümlerinin uygulanmasını s |
| `kvkk-171` | evet | [] |  | BİLMİYORUM |
| `kvkk-172` | evet | [] |  | BİLMİYORUM |
| `kvkk-173` | evet | [] |  | BİLMİYORUM |
| `kvkk-174` | evet | [] |  | BİLMİYORUM |
| `kvkk-175` | evet | [] |  | BİLMİYORUM |
| `kvkk-176` | evet | [] |  | BİLMİYORUM |
| `kvkk-177` |  | [3] |  | Veri ihlali bildirim formunda, "a) Veri sorumlusu ve varsa temsilcisinin kimlik ve adres bilgileri" [3], "b) Kişisel verilerin hangi amaçla  |
| `kvkk-178` | evet | [] |  | BİLMİYORUM |
| `k8s-101` | evet | [] |  | BİLMİYORUM |
| `k8s-102` |  | [1, 2] | ✓ | The HorizontalPodAutoscaler controller considers a Pod "not yet ready" if it's unready and transitioned to ready within a short, configurabl |
| `k8s-103` |  | [1, 2] | ✓ | The default value for the `--horizontal-pod-autoscaler-cpu-initialization-period` option is 5 minutes [1]. This means that during this time  |
| `k8s-104` |  | [2] | ✓ | The VPA Recommender analyzes current and historical resource usage data to identify trends, peak usage, and out-of-memory events [2]. It exa |
| `k8s-105` |  | [1, 2, 3] | ✓ | A VerticalPodAutoscaler stores its recommendations in the `.status.recommendation` field of its resource object, which are calculated by the |
| `k8s-106` |  | [1, 2] | ✓ | The group-template hierarchy supports a maximum depth of 4 levels, which means that there are four levels of nesting allowed in the Composit |
| `k8s-107` |  | [1, 2, 3] | ✓ | The CompositePodGroup resource belongs to the `scheduling.k8s.io/v1alpha3` API group, which must be enabled for its use, as stated in source |
| `k8s-108` |  | [1] | ✓ | A device plugin signals that it does not have a NUMA affinity preference for a given device by returning a nil TopologyInfo, indicating that |
| `k8s-109` |  | [1, 2] | ✓ | A Deployment's `.spec.selector` cannot be changed after creation in `apps/v1`, as it is immutable once created, and any attempt to update it |
| `k8s-110` |  | [1, 2] | ✓ | A bare Pod whose labels match an existing ReplicaSet's selector will be immediately acquired by that ReplicaSet [2]. This is because a Repli |
| `k8s-111` |  | [1, 2] | ✓ | You should use a DaemonSet when it is important that a copy of a Pod always runs on all or certain hosts, as this provides node-level functi |
| `k8s-112` |  | [1] | ✓ | The total number of individual attribute values per device (scalar fields plus all list elements combined) is limited to 48 [1]. When any de |
| `k8s-113` |  | [2] | ✓ | Allocating a device with admin access is not exempt from device taints, as an admin must explicitly tolerate all taints to access tainted de |
| `k8s-114` |  | [1] | ✓ | When updating `resourceclaims/driver`, node-local DRA drivers should use the **`associated-node:<verb>`** verb prefix, such as `associated-n |
| `k8s-115` |  | [1, 2] | ✓ | Only one queueSort plugin may be enabled at a time, as stated in the Scheduling Framework > Interfaces > QueueSort section of source [1]. Th |
| `k8s-116` | evet | [] |  | BİLMİYORUM |
| `k8s-117` |  | [1, 2] | ✓ | If a Pod references a PodGroup that does not exist yet, the Pod remains pending until the entire group hierarchy exists in the cluster [1].  |
| `k8s-118` |  | [] |  | Controllers must create objects in this order: first a `Workload` (1), then a `PodGroup` (2), and finally Pods that reference the `PodGroup` |
| `k8s-119` |  | [1, 2, 3] | ✓ | To disable Memory QoS, set the `MemoryQoS` feature gate to `false`, ensure that `memoryReservationPolicy` is unset or set to `None`, and res |
| `k8s-120` |  | [1] | ✓ | Incorrect implementation of liveness probes can lead to cascading failures, resulting in restarting a container under high load [1]. This ca |
| `k8s-121` | evet | [] |  | BİLMİYORUM |
| `k8s-122` |  | [1, 2] | ✓ | If a container has no CPU and memory limits, the downward API exposes the maximum allocatable value for CPU and memory based on the node all |
| `k8s-123` | evet | [] |  | BİLMİYORUM |
| `k8s-125` |  | [1] | ✓ | When a request violates a LimitRange, the API server returns an HTTP status code `403 Forbidden` and a message explaining the constraint tha |
| `k8s-126` |  | [1, 2, 3] | ✓ | If a node's container runtime does not support the `v1` CRI API on Kubernetes 1.26 or later, the kubelet will fail to register and report an |
| `k8s-127` |  | [1] | ✓ | A Windows Pod can only have 1 DNS suffix, which is the DNS suffix associated with that Pod's namespace (example: `mydns.svc.cluster.local`)  |
| `k8s-129` | evet | [] |  | BİLMİYORUM |
| `k8s-131` |  | [1, 3] | ✓ | The minimum Linux kernel version required for cgroup v2 is 5.8 or later, as stated in the requirements section of the cgroup v2 documentatio |
| `k8s-132` |  | [1] | ✓ | A VolumeAttributesClass can define at most 512 parameters, as stated in the documentation for Volume Attributes Classes ([1]). This limit ap |
| `k8s-133` |  | [1, 2] | ✓ | If the Eviction API only returns 429 or 500, you should try aborting or pausing the automated operation causing the issue and investigating  |
| `k8s-134` |  | [2, 3] | ✓ | The `ownerReferences.blockOwnerDeletion` field controls whether specific dependents can block garbage collection from deleting their owner o |
| `k8s-135` |  | [1] | ✓ | Kubernetes provides two main API kinds that can be used to store configuration: ConfigMap and Secret [1]. These mechanisms are designed to a |
| `k8s-136` | evet | [] |  | BİLMİYORUM |
| `k8s-137` |  | [1, 2] |  | When `internalTrafficPolicy` is set to `Local`, kube-proxy only uses node local endpoints for cluster internal traffic, effectively making p |
| `k8s-138` | evet | [] |  | BİLMİYORUM |
| `k8s-139` |  | [1, 3] | ✓ | You can specify the [RuntimeClass](/docs/concepts/containers/runtime-class/) for a Pod to make sure that Kubernetes runs those containers us |
| `k8s-140` |  | [1, 2] | ✓ | The first steps towards enabling custom Topology Aware Routing heuristics were included in the 1.27 release of Kubernetes, which is a limite |
| `k8s-142` |  | [1] | ✓ | The `ExtendedResourceToleration` admission controller automatically adds tolerations for extended resources, ensuring that pods requesting s |
| `k8s-145` |  | [1] | ✓ | Gateway API has four stable API kinds: GatewayClass, Gateway, HTTPRoute, and GRPCRoute [1]. These kinds are interdependent and have relation |
| `k8s-146` |  | [2, 3] | ✓ | When authentication fails, the request is rejected with HTTP status code 401 [2]. This means that the API server returns a 401 error respons |
| `k8s-148` |  | [1, 2] | ✓ | The `kubernetes.io/pv-protection` finalizer prevents accidental deletion of `PersistentVolume` objects when they are in use by a Pod, ensuri |
| `k8s-149` | evet | [] |  | BİLMİYORUM |
| `k8s-150` |  | [1, 2] | ✓ | The maximum length of list items in `compositePodGroupTemplates` and `podGroupTemplates` is 8, as stated by both [1] and [2], which specify  |
| `k8s-151` |  | [1, 2] | ✓ | In-tree controllers set `DisableDeclarativeValidation` to avoid checking the same fields twice during validation, allowing the `Validate` ca |
| `k8s-161` |  | [2] | ✓ | Bir Pod kaynak isteği LimitRange'i ihlal ederse API sunucusu 403 Forbidden status kodunu döner. Bu durum, bir LimitRange'in kısıtlamalarını  |
| `k8s-162` |  | [1] | ✓ | Cgroup v2 için en düşük Linux çekirdek sürümü 5.8'dir. [1] |
| `k8s-163` |  | [1] | ✓ | Windows üzerinde çalışan bir Pod, en fazla 3 DNS sunucusuna sahip olabilir. Bu sunucular, Pod'un namespace'ine bağlı olan tek bir DNS sunucu |
| `k8s-164` |  | [1] | ✓ | Gateway API'de dört stable API türü vardır: GatewayClass, Gateway, HTTPRoute ve GRPCRoute. Bu türler, organizasyonun rol-oriented doğası içi |
| `k8s-165` |  | [1] |  | Kimlik doğrulama başarısız olursa API sunucusu 401 HTTP kodunu döner. Bu kod, "Yönetici yetkisi unavailable" anlamına gelir ve API sunucusun |
| `k8s-166` | evet | [] |  | BİLMİYORUM |
| `k8s-167` |  | [1] |  | Bir Pod'un başvurduğu PodGroup henüz yoksa, o Pod pending olarak kalır. [1] |
| `k8s-168` | evet | [] |  | BİLMİYORUM |
| `k8s-171` |  | [1, 2] | ✓ | The group-template hierarchy supports a maximum depth of 4 levels [1] and is strictly capped at a maximum of 8 items in lists such as `compo |
| `k8s-172` | evet | [] |  | BİLMİYORUM |
| `k8s-173` | evet | [] |  | BİLMİYORUM |
| `k8s-174` |  | [1, 2, 3] | ✓ | A PodGroup must have a `spec.schedulingPolicy` field defined before it can use a podGroupTemplateRef, and this policy would be copied from t |
| `k8s-175` | evet | [] |  | BİLMİYORUM |
| `k8s-176` |  | [1, 2, 3] | ✓ | The `kubernetes.io/pv-protection` finalizer protects a PersistentVolume by preventing accidental deletion of the object when it is in use by |
| `k8s-177` |  | [2, 3] |  | The Resource manager uses the Topology Manager's data to make resource assignment decisions [2]. A device plugin sends its `TopologyInfo` st |
| `k8s-178` |  | [1] |  | A workload should be a DaemonSet when it needs to run as a system daemon on a specific node and provide facilities that are local to that no |
| `k8s-179` |  | [1, 3] | ✓ | The total length of the parameters object including its keys and values cannot exceed 256 KiB for VolumeAttributesClass parameters, as state |
| `k8s-180` |  | [1, 2] | ✓ | The kubelet requires that the container runtime supports the `v1` CRI API for cgroup v2 to work, which is a requirement since Kubernetes ver |
| `k8s-181` |  | [1, 2] | ✓ | The four stable Gateway API kinds are GatewayClass, Gateway, HTTPRoute, and GRPCRoute [1]. The Service Internal Traffic Policy has two setti |
| `k8s-182` |  | [1, 2, 3] |  | When a resize is deferred, in progress, or infeasible, VPA mode always waits and retries — it never evicts the Pod, regardless of how long t |
| `k8s-183` |  | [2, 3] | ✓ | The total number of individual attribute values per device is limited to 48, which includes scalar fields and list-type elements combined [2 |
| `k8s-184` |  | [2, 3] | ✓ | If you notice stuck evictions, try waiting a while or directly deleting the Pod from your cluster control plane instead of using the Evictio |
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
| `k8s-201` | evet | [] |  | BİLMİYORUM |
| `k8s-202` | evet | [] |  | BİLMİYORUM |
| `k8s-203` | evet | [] |  | BİLMİYORUM |
| `k8s-204` | evet | [] |  | BİLMİYORUM |
