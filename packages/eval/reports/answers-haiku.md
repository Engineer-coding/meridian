# Retrieval değerlendirmesi — answers-haiku

- Tarih: 2026-11-13 · commit `2f61dee-dirty`
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

## Kaynaklı cevap (`anthropic/claude-haiku-5-5`, 3 kaynak)

| Ölçüt | Değer |
|---|---|
| Cevapsız soruda "bilmiyorum" (yüksek iyi) | %100 |
| Cevaplı soruda gereksiz "bilmiyorum" (düşük iyi) | %42 |
| Altın kaynak bağlamda (üst sınır) | %93 |
| Cevap en az bir kaynak gösteriyor | %100 |
| Gösterilen kaynak altın kaynak | %96 |
| Cevap doğru (anahtar kelime, tüm cevaplı sorular) | %54 |
| Cevap doğru (model cevap verdiğinde) | %94 |
| Var olmayan kaynak numarası | %0 |
| Ortanca ilk token / toplam süre | 1.6 sn / 1.5 sn |

| Soru | Bilmiyorum | Kaynak | Altın kaynak gösterildi | Cevap |
|---|---|---|---|---|
| `kvkk-001` |  | [1] | ✓ | Veri sorumlusu, ilgili kişinin başvurusunu talebin niteliğine göre en kısa sürede ve en geç otuz gün içinde ücretsiz olarak sonuçlandırmalıd |
| `kvkk-002` | evet | [] |  | BİLMİYORUM |
| `kvkk-003` | evet | [] |  | BİLMİYORUM |
| `kvkk-004` |  | [1] | ✓ | Kişisel Verileri Koruma Kurulu dokuz üyeden oluşur [1]. Kurulun beş üyesini Türkiye Büyük Millet Meclisi, dört üyesini ise Cumhurbaşkanı seç |
| `kvkk-005` | evet | [] |  | BİLMİYORUM |
| `kvkk-006` |  | [1] | ✓ | Standart sözleşme, imzalanmasından itibaren beş iş günü içinde veri sorumlusu veya veri işleyen tarafından Kuruma bildirilir [1]. Bu süre, s |
| `kvkk-007` | evet | [] |  | BİLMİYORUM |
| `kvkk-008` | evet | [] |  | BİLMİYORUM |
| `kvkk-009` | evet | [] |  | BİLMİYORUM |
| `kvkk-010` | evet | [] |  | BİLMİYORUM |
| `kvkk-011` | evet | [] |  | BİLMİYORUM |
| `kvkk-012` | evet | [] |  | BİLMİYORUM |
| `k8s-001` | evet | [] |  | BİLMİYORUM |
| `k8s-002` | evet | [] |  | BİLMİYORUM |
| `k8s-003` | evet | [] |  | BİLMİYORUM |
| `k8s-004` | evet | [] |  | BİLMİYORUM |
| `k8s-005` | evet | [] |  | BİLMİYORUM |
| `k8s-006` | evet | [] |  | BİLMİYORUM |
| `k8s-007` |  | [1, 3] | ✓ | A brand-new Kubernetes cluster starts with four initial namespaces: default, kube-node-lease, kube-public, and kube-system [1]. The kube-nod |
| `k8s-008` | evet | [] |  | BİLMİYORUM |
| `k8s-009` |  | [1] | ✓ | Yes, the data stored in a ConfigMap cannot exceed 1 MiB [1]. If you need to store settings larger than this, you may consider mounting a vol |
| `k8s-010` | evet | [] |  | BİLMİYORUM |
| `k8s-011` |  | [1, 2, 3] | ✓ | No. In a Job's Pod template, only `Never` or `OnFailure` is allowed; `Always` is not permitted [2]. Also, the restart policy applies to the  |
| `k8s-012` |  | [2] | ✓ | A StatefulSet requires a Headless Service to be responsible for the network identity of its Pods [2]. You are responsible for creating this  |
| `k8s-013` | evet | [] |  | BİLMİYORUM |
| `k8s-014` | evet | [] |  | BİLMİYORUM |
| `k8s-015` |  | [1, 2, 3] | ✓ | If the StorageClass doesn't specify a reclaimPolicy, it defaults to `Delete`, so the dynamically provisioned PersistentVolume inherits that  |
| `k8s-016` | evet | [] |  | BİLMİYORUM |
| `k8s-017` | evet | [] |  | BİLMİYORUM |
| `k8s-018` | evet | [] |  | BİLMİYORUM |
| `kvkk-101` |  | [1] | ✓ | Kişisel Verileri Koruma Kurumunun merkezi Ankara'dadır [1]. |
| `kvkk-103` |  | [1] | ✓ | Kurul, başkan dâhil en az altı üye ile toplanır [1]. Kararlar, üye tam sayısının salt çoğunluğuyla alınır [1]. Kurul üyeleri çekimser oy kul |
| `kvkk-104` | evet | [] |  | BİLMİYORUM |
| `kvkk-105` | evet | [] |  | BİLMİYORUM |
| `kvkk-106` |  | [1] | ✓ | Hayır, Kurul toplantılarındaki görüşmeler aksi kararlaştırılmadıkça gizlidir [1]. Kurulda görüşülen işler tutanağa bağlanır ve kararlar ile  |
| `kvkk-107` |  | [1] | ✓ | Veri sorumlusu, Kurulun istediği bilgi ve belgeleri on beş gün içinde göndermek zorundadır; devlet sırrı niteliğindeki bilgi ve belgeler bu  |
| `kvkk-108` |  | [1, 2, 3] | ✓ | Kurulun giderme kararı, veri sorumlusuna tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde yerine getirilmelidir [1]. Bu düzenleme, |
| `kvkk-109` |  | [1] | ✓ | Kurul, şikâyet üzerine veya resen yapılan incelemede telafisi güç veya imkânsız zararların doğması ve açıkça hukuka aykırılık bulunması hâli |
| `kvkk-110` |  | [1] | ✓ | Açık rıza, belirli bir konuya ilişkin, bilgilendirilmeye dayanan ve özgür iradeyle açıklanan rızadır [1]. |
| `kvkk-111` |  | [1] | ✓ | Veri işleyen, veri sorumlusunun verdiği yetkiye dayanarak onun adına kişisel verileri işleyen gerçek veya tüzel kişidir [1]. |
| `kvkk-112` |  | [1, 2] | ✓ | Anonymization means processing personal data so that, even when combined with other data, it can no longer be associated with an identified  |
| `kvkk-113` |  | [1, 2] | ✓ | Kişisel veriler, ilgili mevzuatta öngörülen veya işlendikleri amaç için gerekli olan süre kadar muhafaza edilebilir [1]. Bu, kişisel veriler |
| `kvkk-114` | evet | [] |  | BİLMİYORUM |
| `kvkk-115` |  | [1, 2, 3] | ✓ | Evet, biyometrik veriler özel nitelikli kişisel veri sayılmaktadır [1]. Bu verilerin işlenmesi, kaynakta sayılan şartların (örneğin ilgili k |
| `kvkk-116` |  | [1] | ✓ | İşlenmesini gerektiren sebepler ortadan kalkmış olsa da kişisel veriler, Kanun ve ilgili diğer kanun hükümlerine uygun olarak işlenmiş olmal |
| `kvkk-117` |  | [1, 2] | ✓ | Yeterlilik kararı, Kurul tarafından verilir ve Resmî Gazete'de yayımlanır [1]. Kurul, gerektiğinde ilgili kurum ve kuruluşların görüşünü alı |
| `kvkk-118` |  | [1, 2] | ✓ | Yeterlilik kararı, en geç dört yılda bir değerlendirilir [2]. Kurul, bu değerlendirme sonucunda veya gerekli gördüğü diğer hallerde kararı i |
| `kvkk-119` |  | [1, 3] | ✓ | Veri sorumlusu, kişisel verilerin elde edilmesi sırasında ilgili kişiye veri sorumlusunun ve varsa temsilcisinin kimliğini, verilerin hangi  |
| `kvkk-120` | evet | [] |  | BİLMİYORUM |
| `kvkk-121` |  | [1, 2] | ✓ | Veri sorumlusu, kendi kurum veya kuruluşunda bu Kanun hükümlerinin uygulanmasını sağlamak amacıyla gerekli denetimleri yapmak veya yaptırmak |
| `kvkk-122` | evet | [] |  | BİLMİYORUM |
| `kvkk-123` |  | [1] | ✓ | Başvurunun veri sorumlusunun hatasından kaynaklanması hâlinde, alınan ücret ilgiliye iade edilir [1]. Ücret, işlemin ayrıca bir maliyeti ger |
| `kvkk-124` | evet | [] |  | BİLMİYORUM |
| `kvkk-125` | evet | [] |  | BİLMİYORUM |
| `kvkk-126` |  | [1] | ✓ | Kişisel verileri işleyen gerçek ve tüzel kişiler, veri işlemeye başlamadan önce Veri Sorumluları Siciline kaydolmak zorundadır [1]. Kurul, i |
| `kvkk-127` |  | [1, 2] | ✓ | Kişisel verileri silmeyen veya anonim hâle getirmeyen kişi, 5237 sayılı Türk Ceza Kanunu'nun 138. maddesine göre cezalandırılır [1]. Bu yükü |
| `kvkk-128` | evet | [] |  | BİLMİYORUM |
| `kvkk-129` |  | [1] | ✓ | Kurulun verdiği idari para cezalarına karşı idare mahkemelerinde dava açılabilir [1]. Bu yol, 2/3/2024 tarihli 7499 sayılı Kanun'un 35. madd |
| `kvkk-130` |  | [1] | ✓ | Kurul üyesi olabilmek için en az dört yıllık lisans düzeyinde yükseköğrenim görmüş olmak gerekir [1]. Ayrıca kurumun görev alanındaki konula |
| `kvkk-131` | evet | [] |  | BİLMİYORUM |
| `kvkk-132` |  | [1] | ✓ | Hayır, Kurul üyeleri özel bir kanuna dayanmadıkça Kuruldaki resmî görevlerinin dışında ticaretle uğraşamaz [1]. Aynı hüküm uyarınca üyeler r |
| `kvkk-133` | evet | [] |  | BİLMİYORUM |
| `kvkk-134` |  | [1] | ✓ | Kurumda daire başkanlıklarının sayısı yediyi geçemez [1]. Başkanlık, görevlerini daire başkanlıkları şeklinde teşkilatlanan hizmet birimleri |
| `kvkk-135` | evet | [] |  | BİLMİYORUM |
| `kvkk-136` |  | [1] | ✓ | Madde 28/1-a uyarınca, kişisel verilerin üçüncü kişilere verilmemek ve veri güvenliğine ilişkin yükümlülüklere uyulmak kaydıyla gerçek kişil |
| `kvkk-137` |  | [1] | ✓ | Kurumun gelirleri arasında genel bütçeden yapılacak hazine yardımları, kuruma ait taşınır ve taşınmazlardan elde edilen gelirler, alınan bağ |
| `kvkk-151` | evet | [] |  | BİLMİYORUM |
| `kvkk-152` | evet | [] |  | BİLMİYORUM |
| `kvkk-153` | evet | [] |  | BİLMİYORUM |
| `kvkk-154` | evet | [] |  | BİLMİYORUM |
| `kvkk-155` | evet | [] |  | BİLMİYORUM |
| `kvkk-156` |  | [1, 2, 3] | ✓ | Kurul, üyeleri arasından Başkan ve İkinci Başkanı seçer ve Kurulun Başkanı aynı zamanda Kurumun da başkanıdır [3]. Başkan, Kurul ve Kurumun  |
| `kvkk-157` | evet | [] |  | BİLMİYORUM |
| `kvkk-158` |  | [1] | ✓ | Veri güvenliğine ilişkin gerekli teknik ve idari tedbirleri alma yükümlülüğü veri sorumlusuna aittir [1]. Veri sorumlusu, kişisel verilerin  |
| `kvkk-171` | evet | [] |  | BİLMİYORUM |
| `kvkk-172` | evet | [] |  | BİLMİYORUM |
| `kvkk-173` | evet | [] |  | BİLMİYORUM |
| `kvkk-174` | evet | [] |  | BİLMİYORUM |
| `kvkk-175` | evet | [] |  | BİLMİYORUM |
| `kvkk-176` | evet | [] |  | BİLMİYORUM |
| `kvkk-177` | evet | [] |  | BİLMİYORUM |
| `kvkk-178` | evet | [] |  | BİLMİYORUM |
| `k8s-101` |  | [1] | ✓ | The aggregation layer proxies requests based on APIService objects: you register an APIService, which "claims" a URL path in the Kubernetes  |
| `k8s-102` | evet | [] |  | BİLMİYORUM |
| `k8s-103` |  | [1, 2] | ✓ | The default of the `--horizontal-pod-autoscaler-cpu-initialization-period` option is 5 minutes [1]. It defines the time window after a Pod s |
| `k8s-104` | evet | [] |  | BİLMİYORUM |
| `k8s-105` |  | [1, 3] | ✓ | A VerticalPodAutoscaler stores its recommendations in the `.status.recommendation` field of the VPA resource [1]. In the Off update mode, th |
| `k8s-106` | evet | [] |  | BİLMİYORUM |
| `k8s-107` |  | [1] | ✓ | The CompositePodGroup resource belongs to the `scheduling.k8s.io/v1alpha3` API group [1]. Your cluster must have this API group enabled, alo |
| `k8s-108` |  | [1] | ✓ | A device plugin that returns a nil TopologyInfo signals that it has no NUMA affinity preference for that device [1]. An empty list of NUMA n |
| `k8s-109` |  | [1, 2, 3] | ✓ | No. In apps/v1, a Deployment's `.spec.selector` is immutable after creation and cannot be updated via `kubectl patch`, `kubectl edit`, `kube |
| `k8s-110` |  | [2, 3] | ✓ | A bare Pod (one with no owner reference) whose labels match a ReplicaSet's selector will be immediately acquired by that ReplicaSet [3]. Bec |
| `k8s-111` |  | [1, 3] | ✓ | Use a DaemonSet when a copy of a Pod must always run on all or certain nodes, especially when it provides node-level functionality that othe |
| `k8s-112` |  | [1] | ✓ | The total number of individual attribute values per device, counting scalar fields and all list elements combined, is limited to 48 [1]. |
| `k8s-113` |  | [2] | ✓ | No. Allocating a device with admin access is not exempt from taints; an admin using that mode must explicitly tolerate all taints to access  |
| `k8s-114` | evet | [] |  | BİLMİYORUM |
| `k8s-115` |  | [1, 2] | ✓ | Only one queueSort plugin may be enabled in the scheduler at a time [1][2]. Because any plugin using the queueSort extension point should be |
| `k8s-116` |  | [1, 3] |  | The sources state that every PodGroup must declare a scheduling policy in its `spec.schedulingPolicy` field, which dictates how the schedule |
| `k8s-117` |  | [1, 2] | ✓ | If a Pod references a PodGroup that does not yet exist, the Pod remains pending [1]. The scheduler automatically queues the Pod for scheduli |
| `k8s-118` |  | [1, 2] | ✓ | Controllers must create the objects in this order: first the Workload, which is the scheduling policy template, then the PodGroup, which is  |
| `k8s-119` |  | [1] | ✓ | To disable Memory QoS, set the `MemoryQoS` feature gate to `false`, ensure `memoryReservationPolicy` is unset or set to `None`, and restart  |
| `k8s-120` |  | [1, 2, 3] | ✓ | If liveness probes are implemented incorrectly, it can lead to cascading failures: containers may restart under high load, client requests c |
| `k8s-121` |  | [1, 2] | ✓ | A Pod with setHostnameAsFQDN whose FQDN is longer than 64 characters fails to start and remains in Pending status (ContainerCreating in kube |
| `k8s-122` | evet | [] |  | BİLMİYORUM |
| `k8s-123` | evet | [] |  | BİLMİYORUM |
| `k8s-125` |  | [1] | ✓ | The API server returns HTTP status code 403 Forbidden, along with a message explaining the violated constraint [1]. |
| `k8s-126` |  | [1, 2] | ✓ | The kubelet will not register the node if the container runtime does not support the v1 CRI API on Kubernetes v1.26 and later [2]. During an |
| `k8s-127` |  | [1] | ✓ | A Windows Pod can have only one DNS suffix, which is the DNS suffix associated with that Pod's namespace (for example, `default.svc.cluster. |
| `k8s-129` |  | [1] | ✓ | DNS and route settings for Windows containers are stored in the Windows registry database rather than as files inside `/etc` as on Linux [1] |
| `k8s-131` |  | [1] | ✓ | The minimum Linux kernel version required for cgroup v2 is 5.8 or later [1]. |
| `k8s-132` |  | [1] | ✓ | A VolumeAttributesClass can define at most 512 parameters, and their total length including keys and values cannot exceed 256 KiB [1]. |
| `k8s-133` | evet | [] |  | BİLMİYORUM |
| `k8s-134` |  | [1, 2, 3] | ✓ | The `ownerReference.blockOwnerDeletion` field, when set to `true`, makes a dependent block foreground deletion of its owner, and only depend |
| `k8s-135` |  | [1] | ✓ | Kubernetes mainly provides ConfigMap and Secret for storing configuration that Pods or other components can load and use [1]. The special-us |
| `k8s-136` | evet | [] |  | BİLMİYORUM |
| `k8s-137` |  | [1, 2] |  | Setting `.spec.internalTrafficPolicy` to `Local` makes kube-proxy use only node-local endpoints for cluster-internal traffic [1]. For Pods o |
| `k8s-138` |  | [1, 2, 3] | ✓ | The default value of `internalTrafficPolicy` is `Cluster`; when it is not set, Kubernetes considers all endpoints [3]. Setting it to `Local` |
| `k8s-139` |  | [1, 3] | ✓ | You can use a RuntimeClass to specify the particular container runtime that Kubernetes should use for a Pod [3]. A RuntimeClass lets you run |
| `k8s-140` |  | [1] | ✓ | The first steps to enable custom heuristics were included in the 1.27 release [1]. This was a limited implementation that may not yet cover  |
| `k8s-142` | evet | [] |  | BİLMİYORUM |
| `k8s-145` | evet | [] |  | BİLMİYORUM |
| `k8s-146` |  | [2] | ✓ | When authentication fails, the API server rejects the request with HTTP status code 401 [2]. |
| `k8s-148` |  | [1, 2] | ✓ | The kubernetes.io/pv-protection finalizer prevents accidental deletion of a PersistentVolume object while it is in use by a Pod [2]. When so |
| `k8s-149` | evet | [] |  | BİLMİYORUM |
| `k8s-150` |  | [1, 2] | ✓ | The question asks about a "maximum length" for list items, but the sources describe a maximum number of items, not a length. Every `composit |
| `k8s-151` |  | [1] | ✓ | In-tree controllers set `DisableDeclarativeValidation` because the API server already runs declarative validation on the embedded building b |
| `k8s-161` |  | [1, 2] | ✓ | API sunucusu, bir Pod'un LimitRange kısıtını ihlal eden isteğini HTTP `403 Forbidden` durum kodu ve ihlal edilen kısıtı açıklayan bir mesajl |
| `k8s-162` |  | [1] | ✓ | cgroup v2 için en düşük Linux çekirdek sürümü 5.8'dir [1]. Bu gereksinimin yanında işletim sistemi dağıtımının cgroup v2'yi etkinleştirmiş o |
| `k8s-163` |  | [1] | ✓ | Windows üzerinde çalışan bir Pod yalnızca tek bir DNS sonekine sahip olabilir; bu sonek, Pod'un namespace'ine ait olan sonektir (örneğin `de |
| `k8s-164` |  | [1] | ✓ | Gateway API'de dört kararlı API türü vardır: GatewayClass, Gateway, HTTPRoute ve GRPCRoute [1]. |
| `k8s-165` |  | [3] | ✓ | Kimlik doğrulama başarısız olursa, istek reddedilir ve API sunucusu HTTP 401 durum kodunu döner [3]. |
| `k8s-166` |  | [1] | ✓ | Bir VolumeAttributesClass için en fazla 512 parametre tanımlanabilir [1]. Parametrelerin ve anahtar-değerlerinin toplam uzunluğu ise 256 KiB |
| `k8s-167` |  | [1] |  | Bir Pod'un başvurduğu PodGroup henüz yoksa Pod beklemede (pending) kalır ve zamanlama başlamaz [1]. Ayrıca PodGroup'un üst CompositePodGroup |
| `k8s-168` |  | [1, 2] | ✓ | `internalTrafficPolicy` alanının varsayılan değeri `Cluster`'dır; kaynaklara göre bu alan ayarlanmadığında da Kubernetes tüm endpoint'leri d |
| `k8s-171` | evet | [] |  | BİLMİYORUM |
| `k8s-172` | evet | [] |  | BİLMİYORUM |
| `k8s-173` | evet | [] |  | BİLMİYORUM |
| `k8s-174` | evet | [] |  | BİLMİYORUM |
| `k8s-175` | evet | [] |  | BİLMİYORUM |
| `k8s-176` | evet | [] |  | BİLMİYORUM |
| `k8s-177` | evet | [] |  | BİLMİYORUM |
| `k8s-178` |  | [1, 2, 3] | ✓ | A workload should be a DaemonSet when it provides facilities local to a specific node, such as a driver or node-level service, and it must r |
| `k8s-179` |  | [1] | ✓ | A VolumeAttributesClass can define at most 512 parameters, and the total length of its parameters object, including keys and values, cannot  |
| `k8s-180` | evet | [] |  | BİLMİYORUM |
| `k8s-181` | evet | [] |  | BİLMİYORUM |
| `k8s-182` | evet | [] |  | BİLMİYORUM |
| `k8s-183` | evet | [] |  | BİLMİYORUM |
| `k8s-184` | evet | [] |  | BİLMİYORUM |
| `k8s-185` |  | [1, 3] | ✓ | Bir Service'in `internalTrafficPolicy` değeri `Local` olduğunda kube-proxy yalnızca aynı node üzerindeki (node local) endpoint'lere yönlendi |
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
