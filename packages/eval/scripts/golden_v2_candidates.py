"""Altın set v2 adayları: 120 yeni soru ve mevcut 23 cevaplı soru için cevap anahtar kelimeleri.

Her aday kaynaktan birebir bir kanıt cümlesi taşır (`meridian_ai.evaluation.candidates`
denetler). `keywords`: her iç liste "bunlardan biri
cevapta geçmeli" demektir; cevap doğruluğu metriğinin girdisidir. Adaylar Claude tarafından
korpus okunarak yazılmıştır: insan onayına kadar `origin: synthetic`, `verified: false`.
"""

C = "content/en/docs/concepts/"
K = "kvkk/6698.md"
W = C + "workloads/"
P = W + "pods/"
SN = C + "services-networking/"
SE = C + "scheduling-eviction/"
ST = C + "storage/"
OV = C + "overview/working-with-objects/"
CA = C + "cluster-administration/"
AR = C + "architecture/"
DRA = C + "resource-management/dynamic-resource-allocation/"


def s(question, answer, sources, keywords, lang=None, corpus=None):
    return ("single_hop", question, answer, sources, keywords, lang, corpus)


def m(question, answer, sources, keywords, lang=None, corpus=None):
    return ("multi_hop", question, answer, sources, keywords, lang, corpus)


def u(question, note, forbidden, lang=None, corpus=None):
    """Cevapsız soru: `forbidden` terimlerinin korpusta (ilgili anlamda) geçmediği denetlenir."""
    return ("unanswerable", question, None, [], note, lang, corpus, forbidden)


KVKK = [
    s("Kişisel Verileri Koruma Kurumunun merkezi neresidir?", "Ankara.", [(K, "Madde 19", "Kurumun merkezi Ankara’dadır")], [["ankara"]]),
    s("Kurumun karar organı hangisidir?", "Kurul.", [(K, "Madde 19", "Kurumun karar organı Kuruldur")], [["kurul"]]),
    s("Kurul toplantı yapabilmek için en az kaç üyeyle toplanır ve kararı nasıl alır?", "Başkan dâhil en az altı üyeyle toplanır, üye tam sayısının salt çoğunluğuyla karar alır.", [(K, "Madde 23", "Kurul, başkan dâhil en az altı üye ile toplanır")], [["altı", "6"], ["salt çoğunluk"]]),
    s("Kurul üyeleri oylamada çekimser kalabilir mi?", "Hayır, Kurul üyeleri çekimser oy kullanamaz.", [(K, "Madde 23", "Kurul üyeleri çekimser oy kullanamaz")], [["kullanamaz", "hayır", "kalamaz"]]),
    s("Kurul kararları ve karşı oy gerekçeleri en geç ne kadar sürede yazılır?", "Karar tarihinden itibaren en geç on beş gün içinde.", [(K, "Madde 23", "karar tarihinden itibaren en geç on beş gün içinde yazılır")], [["on beş", "15"]]),
    s("Kurul toplantılarındaki görüşmeler herkese açık mı?", "Hayır; aksi kararlaştırılmadıkça görüşmeler gizlidir.", [(K, "Madde 23", "Kurul toplantılarındaki görüşmeler gizlidir")], [["gizli"]]),
    s("Kurul inceleme sırasında belge isterse veri sorumlusunun göndermek için kaç günü vardır?", "On beş gün.", [(K, "Madde 15", "bilgi ve belgeleri on beş gün içinde göndermek")], [["on beş", "15"]]),
    s("Kurul verdiği giderme kararının veri sorumlusu tarafından ne zaman yerine getirilmesi gerekir?", "Tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde.", [(K, "Madde 15", "tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde yerine getirilir")], [["otuz", "30"]]),
    s("Kurul hangi durumda veri işlemenin durdurulmasına karar verebilir?", "Telafisi güç veya imkânsız zararların doğması ve açıkça hukuka aykırılık olması hâlinde.", [(K, "Madde 15", "telafisi güç veya imkânsız zararların doğması ve açıkça hukuka aykırılık olması")], [["telafisi", "hukuka aykırılık"]]),
    s("Kanuna göre açık rıza nasıl tanımlanır?", "Belirli bir konuya ilişkin, bilgilendirilmeye dayanan ve özgür iradeyle açıklanan rıza.", [(K, "Madde 3", "Belirli bir konuya ilişkin, bilgilendirilmeye dayanan ve özgür iradeyle açıklanan rızayı")], [["özgür irade"], ["bilgilendirilme"]]),
    s("Veri işleyen kimdir?", "Veri sorumlusunun verdiği yetkiye dayanarak onun adına kişisel verileri işleyen gerçek veya tüzel kişi.", [(K, "Madde 3", "Veri sorumlusunun verdiği yetkiye dayanarak onun adına kişisel verileri işleyen gerçek veya tüzel kişiyi")], [["adına"], ["yetki"]]),
    s("Anonim hâle getirme ne demektir?", "Verilerin, başka verilerle eşleştirilerek dahi kimliği belirli veya belirlenebilir bir gerçek kişiyle ilişkilendirilemeyecek hâle getirilmesi.", [(K, "Madde 3", "başka verilerle eşleştirilerek dahi hiçbir surette kimliği belirli veya belirlenebilir bir gerçek kişiyle ilişkilendirilemeyecek")], [["ilişkilendirilemeyecek", "ilişkilendirilemez"]]),
    s("Kişisel veriler ne kadar süreyle muhafaza edilebilir, kanunun genel ilkesi nedir?", "İlgili mevzuatta öngörülen veya işlendikleri amaç için gerekli olan süre kadar.", [(K, "Madde 4", "işlendikleri amaç için gerekli olan süre kadar muhafaza edilme")], [["gerekli olan süre"]]),
    s("Bir sözleşmenin ifası için müşterinin verisini işlemek açık rıza gerektirir mi?", "Hayır; sözleşmenin kurulması veya ifasıyla doğrudan ilgili olması kaydıyla sözleşme taraflarının verileri açık rıza aranmaksızın işlenebilir.", [(K, "Madde 5", "Bir sözleşmenin kurulması veya ifasıyla doğrudan doğruya ilgili olması kaydıyla")], [["sözleşme"], ["aranmaksızın", "gerekmez", "hayır", "gerektirmez"]]),
    s("Biyometrik veri özel nitelikli kişisel veri midir?", "Evet, biyometrik ve genetik veriler özel nitelikli kişisel veridir.", [(K, "Madde 6", "biyometrik ve genetik verileri özel nitelikli kişisel veridir")], [["evet", "özel nitelikli"]]),
    s("İşlenme sebebi ortadan kalkan kişisel verilere ne yapılır?", "Resen veya ilgili kişinin talebi üzerine veri sorumlusu tarafından silinir, yok edilir veya anonim hâle getirilir.", [(K, "Madde 7", "resen veya ilgili kişinin talebi üzerine veri sorumlusu tarafından silinir, yok edilir veya anonim hâle getirilir")], [["silinir", "silinmesi"], ["anonim"]]),
    s("Yurt dışı aktarımı için yeterlilik kararını kim verir ve nerede yayımlanır?", "Kurul verir, Resmî Gazete'de yayımlanır.", [(K, "Madde 9", "Yeterlilik kararı, Kurul tarafından verilir")], [["kurul"], ["resmî gazete", "resmi gazete"]]),
    s("Yeterlilik kararı ne sıklıkta değerlendirilir?", "En geç dört yılda bir.", [(K, "Madde 9", "en geç dört yılda bir değerlendirilir")], [["dört", "4"]]),
    s("Aydınlatma yükümlülüğü kapsamında ilgili kişiye neler söylenmelidir?", "Veri sorumlusunun kimliği, işleme amacı, aktarılacağı kişiler ve amaç, toplama yöntemi ve hukuki sebep ile 11. maddedeki haklar.", [(K, "Madde 10", "Kişisel verilerin hangi amaçla işleneceği")], [["amaç"], ["kimliği", "hukuki sebep", "yöntemi"]]),
    s("Kanuna aykırı veri işleme yüzünden zarara uğrayan kişinin hakkı nedir?", "Zararın giderilmesini talep etme hakkı vardır.", [(K, "Madde 11", "zarara uğraması hâlinde zararın giderilmesini talep etme")], [["zarar"], ["giderilmesi"]]),
    s("Veri sorumlusu kendi kurumunda kanuna uyumu nasıl sağlamak zorundadır?", "Gerekli denetimleri yapmak veya yaptırmak zorundadır.", [(K, "Madde 12", "gerekli denetimleri yapmak veya yaptırmak zorundadır")], [["denetim"]]),
    s("Çalışan işten ayrıldıktan sonra öğrendiği kişisel verileri açıklayabilir mi?", "Hayır; açıklama yasağı görevden ayrıldıktan sonra da devam eder.", [(K, "Madde 12", "Bu yükümlülük görevden ayrılmalarından sonra da devam eder")], [["devam", "açıklayamaz"]]),
    s("Başvuru için alınan ücret hangi durumda geri ödenir?", "Başvurunun veri sorumlusunun hatasından kaynaklanması hâlinde iade edilir.", [(K, "Madde 13", "veri sorumlusunun hatasından kaynaklanması hâlinde alınan ücret ilgiliye iade edilir")], [["hata"], ["iade"]]),
    s("Kişilik hakları ihlal edilen kişinin tazminat hakkı şikâyet yolu nedeniyle ortadan kalkar mı?", "Hayır, genel hükümlere göre tazminat hakkı saklıdır.", [(K, "Madde 14", "genel hükümlere göre tazminat hakkı saklıdır")], [["saklı"]]),
    s("Veri Sorumluları Sicilini kim tutar?", "Kurulun gözetiminde Başkanlık tutar.", [(K, "Madde 16", "Başkanlık tarafından kamuya açık olarak Veri Sorumluları Sicili tutulur")], [["başkanlık"]]),
    s("Veri sorumlusu sicile ne zaman kaydolmak zorundadır?", "Veri işlemeye başlamadan önce.", [(K, "Madde 16", "veri işlemeye başlamadan önce Veri Sorumluları Siciline kaydolmak zorundadır")], [["başlamadan önce"]]),
    s("Kişisel verileri silmeyen kişi hangi hükme göre cezalandırılır?", "5237 sayılı Türk Ceza Kanununun 138. maddesine göre.", [(K, "Madde 17", "5237 sayılı Kanunun 138 inci maddesine göre cezalandırılır")], [["138"]]),
    s("Aydınlatma yükümlülüğünü yerine getirmeyene ne kadar idari para cezası verilir?", "5.000 TL'den 100.000 TL'ye kadar.", [(K, "Madde 18", "aydınlatma yükümlülüğünü yerine getirmeyenler hakkında 5.000 Türk lirasından 100.000 Türk lirasına kadar")], [["5.000"], ["100.000"]]),
    s("Kurulun verdiği idari para cezasına karşı nereye başvurulur?", "İdare mahkemelerinde dava açılabilir.", [(K, "Madde 18", "idare mahkemelerinde dava açılabilir")], [["idare mahkeme"]]),
    s("Kurul üyesi olmak için hangi eğitim düzeyi gerekir?", "En az dört yıllık lisans düzeyinde yükseköğrenim.", [(K, "Madde 21", "En az dört yıllık lisans düzeyinde yükseköğrenim görmüş olmak")], [["dört yıllık"], ["lisans"]]),
    s("Siyasi parti üyesi biri Kurula üye olabilir mi?", "Hayır, herhangi bir siyasi parti üyesi olmamak şarttır.", [(K, "Madde 21", "Herhangi bir siyasi parti üyesi olmamak")], [["olmamak", "hayır", "olamaz"]]),
    s("Kurul üyesi görevdeyken ticaretle uğraşabilir mi?", "Hayır, ticaretle uğraşamaz; ancak bilimsel yayın yapabilir ve ders verebilir.", [(K, "Madde 21", "ticaretle uğraşamaz")], [["uğraşamaz", "hayır"]]),
    s("Kurum başkanının yokluğunda ona kim vekalet eder?", "İkinci Başkan.", [(K, "Madde 24", "İkinci Başkan, Başkana vekalet eder")], [["ikinci başkan"]]),
    s("Kurumda en fazla kaç daire başkanlığı olabilir?", "Yediyi geçemez.", [(K, "Madde 25", "Daire başkanlıklarının sayısı yediyi geçemez")], [["yedi", "7"]]),
    s("Başkan Yardımcısı olmak için kaç yıl kamu hizmeti gerekir?", "On yıl.", [(K, "Madde 25", "on yıl süreyle kamu hizmetinde bulunan kişiler")], [["on yıl", "10 yıl"]]),
    s("Kişinin kendi ailesiyle ilgili işlediği veriler kanun kapsamında mıdır?", "Hayır; üçüncü kişilere verilmemek ve veri güvenliğine uyulmak kaydıyla aynı konutta yaşayan aile fertleriyle ilgili faaliyetlerde kanun uygulanmaz.", [(K, "Madde 28", "aynı konutta yaşayan aile fertleriyle ilgili faaliyetler kapsamında işlenmesi")], [["aile"], ["uygulanmaz", "hayır", "kapsam dışı", "değildir"]]),
    s("Kurumun gelirleri arasında neler vardır?", "Genel bütçeden hazine yardımları, taşınır ve taşınmazlardan gelirler, bağış ve yardımlar ve diğer gelirler.", [(K, "Madde 29", "Genel bütçeden yapılacak hazine yardımları")], [["hazine", "genel bütçe"]]),
]

KVKK_MULTI = [
    m("Veri Sorumluları Siciline kaydolmayan bir şirket ne zaman kaydolmalıydı ve hangi ceza uygulanır?", "Veri işlemeye başlamadan önce kaydolmalıydı; 20.000 TL'den 1.000.000 TL'ye kadar idari para cezası uygulanır.", [(K, "Madde 16", "veri işlemeye başlamadan önce Veri Sorumluları Siciline kaydolmak zorundadır"), (K, "Madde 18", "Veri Sorumluları Siciline kayıt ve bildirim yükümlülüğüne aykırı hareket edenler hakkında 20.000 Türk lirasından")], [["başlamadan önce"], ["20.000"]]),
    m("Standart sözleşmeyi Kuruma bildirmeyen bir veri işleyene hangi ceza verilir, bildirim kime yapılmalıydı?", "Kuruma bildirilmeliydi; 50.000 TL'den 1.000.000 TL'ye kadar idari para cezası verilir.", [(K, "Madde 9", "veri sorumlusu veya veri işleyen tarafından Kuruma bildirilir"), (K, "Madde 18", "bildirim yükümlülüğünü")], [["kurum"], ["50.000"]]),
    m("Kurulun giderme kararını süresinde uygulamayan veri sorumlusunun süresi neydi ve cezası nedir?", "Tebliğden itibaren en geç otuz gün; 25.000 TL'den 1.000.000 TL'ye kadar idari para cezası.", [(K, "Madde 15", "tebliğden itibaren gecikmeksizin ve en geç otuz gün içinde yerine getirilir"), (K, "Madde 18", "Kurul tarafından verilen kararları yerine getirmeyenler hakkında 25.000 Türk lirasından")], [["otuz", "30"], ["25.000"]]),
    m("Veri sorumlusu başvuruya 30 gün içinde cevap vermezse ilgili kişi ne yapabilir ve bunun için en fazla ne kadar süresi vardır?", "Kurula şikâyette bulunabilir; her hâlde başvuru tarihinden itibaren altmış gün içinde.", [(K, "Madde 13", "en geç otuz gün içinde ücretsiz olarak sonuçlandırır"), (K, "Madde 14", "başvuru tarihinden itibaren altmış gün içinde Kurula şikâyette bulunabilir")], [["şikâyet", "şikayet"], ["altmış", "60"]]),
    m("Silinmesi gereken kişisel verileri silmemenin dayanağı ve cezai sonucu nedir?", "Silme yükümlülüğü 7. maddededir; silmeyenler TCK 138. maddeye göre cezalandırılır.", [(K, "Madde 7", "veri sorumlusu tarafından silinir, yok edilir veya anonim hâle getirilir"), (K, "Madde 17", "5237 sayılı Kanunun 138 inci maddesine göre cezalandırılır")], [["138"], ["sil"]]),
    m("Kişisel Verileri Koruma Kurulunun başkanı nasıl belirlenir ve Kurum içindeki rolü nedir?", "Kurul üyeleri kendi aralarından seçer; Kurulun Başkanı Kurumun da başkanı ve en üst amiridir.", [(K, "Madde 21", "Kurul, üyeleri arasından Başkan ve İkinci Başkanı seçer"), (K, "Madde 24", "Kurumun en üst amiri")], [["üyeleri arasından", "kendi arasından"], ["amir", "başkanıdır", "kurumun başkan"]]),
    m("Özel nitelikli verileri işlerken alınması gereken önlemleri kim belirler ve bu kanunun hangi görev listesinde geçer?", "Kurul belirler; hem 6. maddede hem Kurulun görevleri arasında (22. madde) sayılır.", [(K, "Madde 6", "Kurul tarafından belirlenen yeterli önlemlerin alınması şarttır"), (K, "Madde 22", "Özel nitelikli kişisel verilerin işlenmesi için aranan yeterli önlemleri belirlemek")], [["kurul"], ["önlem"]]),
    m("Veri güvenliği yükümlülüklerini kim belirler ve veri işleyen şirketin ihlalinde veri sorumlusu sorumlu mudur?", "Kurul düzenleyici işlemle belirler; veri sorumlusu, verileri kendi adına işleyen kişiyle birlikte müştereken sorumludur.", [(K, "Madde 22", "Veri güvenliğine ilişkin yükümlülükleri belirlemek amacıyla düzenleyici işlem yapmak"), (K, "Madde 12", "bu kişilerle birlikte müştereken sorumludur")], [["kurul"], ["müştereken"]]),
]

KVKK_NONE = [
    u("Kanuna göre şirketlerin veri koruma görevlisi (DPO) ataması zorunlu mu?", "Yakın ıska: kanun DPO düzenlemez; 'Veri Koruma Uzmanı' Kurum personelidir.", ["veri koruma görevlisi", "dpo"]),
    u("Çerez (cookie) kullanmak için kullanıcıdan nasıl rıza alınmalıdır?", "Çerezden hiç söz edilmez.", ["çerez", "cookie"]),
    u("Çocukların kişisel verilerinin işlenmesinde veli izni kaç yaşına kadar gerekir?", "Çocuk verisi için özel hüküm yok.", ["çocuk", "veli"]),
    u("Kanundaki idari para cezaları şirketin yıllık cirosunun yüzde kaçına kadar çıkabilir?", "Cezalar sabit tutarlıdır, ciroya bağlı değildir.", ["ciro"]),
    u("Yapay zekâ sistemlerine kişisel veri vermek için Kurulun özel bir izni gerekir mi?", "Yapay zekâ geçmez.", ["yapay zek"]),
    u("Kurumun bu yılki toplam bütçesi kaç milyon liradır?", "Yalnızca bütçenin usulü düzenlenir, tutar yok.", ["milyon"]),
    u("Veri ihlali bildirim formunda hangi alanlar doldurulmalıdır?", "Bildirim yükümlülüğü var ama form tanımlı değil.", ["bildirim formu"]),
    u("Kişisel Verileri Koruma Uzmanı olmak için KPSS puanı kaç olmalıdır?", "Uzman kadrosu var, sınav puanı yok.", ["kpss"]),
]

K8S = [
    s("How does the aggregation layer know which API paths to proxy to an extension API server?", "You add an APIService object, which claims the URL path; the aggregation layer then proxies anything sent to it to the registered APIService.", [(C + "extend-kubernetes/api-extension/apiserver-aggregation.md", "Aggregation layer", 'To register an API, you add an _APIService_')], [["apiservice"]]),
    s("What is the default value of --horizontal-pod-autoscaler-initial-readiness-delay?", "30 seconds.", [(W + "autoscaling/horizontal-pod-autoscale.md", "Algorithm details", "and its default is 30 seconds")], [["30"]]),
    s("What is the default of the HPA --horizontal-pod-autoscaler-cpu-initialization-period option?", "5 minutes.", [(W + "autoscaling/horizontal-pod-autoscale.md", "Algorithm details", "and its default is 5 minutes")], [["5 min", "five min"]]),
    s("Which three types of recommendation does the VPA Recommender calculate?", "Target, lower bound and upper bound.", [(W + "autoscaling/vertical-pod-autoscale.md", "How does a VerticalPodAutoscaler work?", "the Recommender calculates three types of recommendations")], [["target"], ["lower"], ["upper"]]),
    s("Where does a VerticalPodAutoscaler store its recommendations?", "In the resource's .status.recommendation field.", [(W + "autoscaling/vertical-pod-autoscale.md", "How does a VerticalPodAutoscaler work?", "status.recommendation")], [["status.recommendation", "status recommendation"]]),
    s("What is the maximum nesting depth of the CompositePodGroup template hierarchy?", "4 levels.", [(W + "compositepodgroup-api/lifecycle.md", "Limitations and validation rules", "supports a maximum depth of 4 levels")], [["4", "four"]]),
    s("Which API group does the CompositePodGroup resource belong to?", "scheduling.k8s.io/v1alpha3.", [(W + "compositepodgroup-api/_index.md", "What is a CompositePodGroup?", "scheduling.k8s.io/v1alpha3")], [["scheduling.k8s.io"]]),
    s("What does a device plugin signal by returning a nil TopologyInfo?", "That it has no NUMA affinity preference for that device.", [(C + "extend-kubernetes/compute-storage-net/device-plugins.md", "Device plugin integration with the Topology Manager", "does not have a NUMA affinity preference")], [["numa"], ["no ", "not ", "without"]]),
    s("Can a Deployment's .spec.selector be changed after creation in apps/v1?", "No, it is immutable after creation.", [(W + "controllers/deployment.md", "Selector", "is immutable after creation")], [["immutable", "cannot", "no,"]]),
    s("What happens to a bare Pod whose labels match an existing ReplicaSet's selector?", "The ReplicaSet acquires it, and if over its desired count the Pod is immediately terminated.", [(W + "controllers/replicaset.md", "Non-Template Pod acquisitions", "they will immediately be acquired by it")], [["acquire"]]),
    s("When should I use a DaemonSet rather than a Deployment?", "When a copy of a Pod must always run on all or certain hosts, providing node-level functionality.", [(W + "controllers/daemonset.md", "Deployments", "Use a DaemonSet when it is important that a copy of a Pod always run on")], [["node", "host"], ["all", "every", "certain"]]),
    s("How many attribute values per device are allowed with DRA list-type attributes?", "48 in total, scalar fields plus list elements.", [(DRA + "dra-api.md", "Details for DRA Driver Authors", "is limited to **48**")], [["48"]]),
    s("Is a device allocated with admin access exempt from device taints?", "No; an admin must explicitly tolerate all taints to access tainted devices.", [(DRA + "device-taints.md", "Device taints and tolerations", "is not exempt either")], [["tolerate", "not exempt", "no,"]]),
    s("Which verb prefix should node-local DRA drivers use when updating resourceclaims/driver?", "associated-node, for example associated-node:update.", [(C + "security/hardening-guide/dynamic-resource-allocation.md", "Node-aware DRA verbs", "associated-node:update")], [["associated-node"]]),
    s("How many queueSort plugins can be enabled in the scheduler at a time?", "Exactly one.", [(C + "security/hardening-guide/scheduler.md", "Key considerations", "Exactly one plugin that uses the `queueSort` extension point can be enabled at a time")], [["one", "1"]]),
    s("Which scheduling policies can a PodGroup carry?", "basic or gang.", [(W + "podgroup-api/_index.md", "Scheduling policy", "or `gang`) in `spec.schedulingPolicy`")], [["basic"], ["gang"]]),
    s("What happens if a Pod references a PodGroup that does not exist yet?", "It stays pending; the scheduler queues it once the PodGroup is created.", [(W + "podgroup-api/lifecycle.md", "Creation ordering", "the `Pod` remains pending")], [["pending"]]),
    s("In what order must controllers create Workload, PodGroup and Pods?", "Workload first, then PodGroup, then Pods.", [(W + "podgroup-api/lifecycle.md", "Creation ordering", "Controllers must create objects in this order")], [["workload"], ["podgroup"], ["pod"]]),
    s("How do I disable Memory QoS?", "Set the MemoryQoS feature gate to false, make sure memoryReservationPolicy is unset or None, and restart the kubelet.", [(P + "pod-qos.md", "Disabling or rolling back Memory QoS", "set the `MemoryQoS` feature gate to `false`")], [["memoryqos"], ["false"], ["restart"]]),
    s("What can happen if liveness probes are implemented incorrectly?", "Cascading failures: containers restart under high load, client requests fail and remaining Pods get more load.", [(P + "probes.md", "Liveness probe", "Incorrect implementation of liveness probes can lead to cascading failures")], [["cascading"]]),
    s("What happens to a Pod with setHostnameAsFQDN whose FQDN is longer than 64 characters?", "It fails to start and stays Pending (ContainerCreating) with error events.", [(P + "pod-hostname.md", "Hostname with pod's setHostnameAsFQDN fields", "it will fail to start")], [["fail"], ["pending", "start"]]),
    s("What does the downward API expose if a container has no CPU and memory limits?", "The maximum allocatable value for CPU and memory, from node allocatable.", [(P + "downward-api.md", "Fallback information for resource limits", "kubelet defaults to exposing the maximum allocatable value")], [["allocatable"]]),
    s("What value does metadata.generation have on a new Pod?", "1; it increments on every update to mutable spec fields.", [(P + "_index.md", "Pod generation", "new pods have a `metadata.generation` of 1")], [["1", "one"]]),
    s("Does a cluster on my own premises have a cloud controller manager?", "No, on-premises or learning environments have none.", [(AR + "_index.md", "cloud-controller-manager", "the cluster does not have a cloud controller manager")], [["no", "not", "does not"]]),
    s("What HTTP status does the API server return when a request violates a LimitRange?", "403 Forbidden, with a message explaining the violated constraint.", [(C + "policy/limit-range.md", "Constraints on resource limits and requests", "code `403 Forbidden`")], [["403"]]),
    s("What happens to a node whose container runtime does not support the v1 CRI API on Kubernetes 1.26 or later?", "The kubelet will not register the node.", [(C + "containers/cri.md", "The API", "the kubelet will not register the node")], [["not register"]]),
    s("How many DNS suffixes can a Windows Pod have?", "Only 1, the suffix associated with the Pod's namespace.", [(SN + "dns-pod-service.md", "DNS resolution on Windows nodes", "you can only have 1 DNS suffix")], [["1", "one", "single"]]),
    s("Is the ClusterFirstWithHostNet DNS policy supported on Windows nodes?", "No, it is not supported for Pods on Windows nodes.", [(SN + "dns-pod-service.md", "DNS resolution on Windows nodes", "`ClusterFirstWithHostNet` is not supported")], [["not supported", "no,"]]),
    s("Where are DNS and route settings stored for Windows containers?", "In the Windows registry database rather than in files under /etc.", [(SN + "windows-networking.md", "Container networking on Windows", "stored in the Windows registry database")], [["registry"]]),
    s("Who does a controller read and update in the controller pattern?", "It typically reads an object's .spec, possibly does things, and updates its .status.", [(C + "extend-kubernetes/_index.md", "Extension patterns", "read an object's `.spec`, possibly do things, and then")], [["spec"], ["status"]]),
    s("What is the minimum Linux kernel version required for cgroup v2?", "5.8 or later.", [(AR + "cgroups.md", "Requirements", "Linux Kernel version is 5.8 or later")], [["5.8"]]),
    s("How many parameters can a VolumeAttributesClass define at most?", "At most 512, and their total length cannot exceed 256 KiB.", [(ST + "volume-attributes-classes.md", "Parameters", "There can be at most 512 parameters")], [["512"]]),
    s("What should I try when the Eviction API only returns 429 or 500?", "Abort or pause the automated operation and investigate, or wait and delete the Pod directly from the control plane.", [(SE + "api-eviction.md", "Troubleshooting stuck evictions", "Abort or pause the automated operation causing the issue")], [["abort", "pause", "delete"]]),
    s("Which ownerReference field makes a dependent block foreground deletion of its owner?", "ownerReference.blockOwnerDeletion=true.", [(AR + "garbage-collection.md", "Foreground cascading deletion", "`ownerReference.blockOwnerDeletion=true`")], [["blockownerdeletion"]]),
    s("Which two API kinds does Kubernetes mainly provide for storing configuration?", "ConfigMap and Secret.", [(C + "configuration/_index.md", "Kubernetes configuration-related APIs", "two main API kinds")], [["configmap"], ["secret"]]),
    s("What does Cluster Autoscaler do when provisioning a new node?", "It adds Nodes to the pre-configured Node group that best fits pending Pods' requests.", [(CA + "node-autoscaling.md", "Cluster Autoscaler", "adds or removes Nodes to pre-configured _Node groups_")], [["node group", "group"]]),
    s("What does internalTrafficPolicy: Local do?", "kube-proxy considers only node-local endpoints.", [(SN + "service-traffic-policy.md", "How it works", "only node local")], [["local"], ["endpoint"]]),
    s("What is the default value of internalTrafficPolicy?", "Cluster.", [(SN + "service-traffic-policy.md", "How it works", "`Cluster` (the default)")], [["cluster"]]),
    s("What can I use to run Pods with a specific container runtime?", "RuntimeClass.", [(C + "containers/_index.md", "Container runtimes", "you can specify the [RuntimeClass]")], [["runtimeclass"]]),
    s("In which Kubernetes version were the first steps toward custom Topology Aware Routing heuristics included?", "1.27.", [(SN + "topology-aware-routing.md", "Custom heuristics", "were included in the 1.27 release")], [["1.27"]]),
    s("Should a mutating admission webhook overwrite array values?", "No; patch only the fields you need and don't overwrite array values.", [(CA + "admission-webhooks-good-practices.md", "Mutation scope and field considerations", "Don't overwrite array values")], [["don't", "do not", "should not", "no,", "avoid"]]),
    s("Which admission controller automatically adds tolerations for extended resources?", "ExtendedResourceToleration.", [(SE + "taint-and-toleration.md", "Example Use Cases", "admission controller will\nautomatically add the correct toleration")], [["extendedresourcetoleration"]]),
    s("Does Kubernetes on Windows support IPv6-only networking?", "No, single-stack IPv6-only is not supported.", [(SN + "dual-stack.md", "Windows support", 'does not support single-stack "IPv6-only" networking')], [["not support", "no,", "does not"]]),
    s("Do overlay (VXLAN) networks on Windows support dual-stack?", "No, they do not.", [(SN + "dual-stack.md", "Windows support", "Overlay (VXLAN) networks on Windows **do not** support dual-stack")], [["not", "no,"]]),
    s("How many stable API kinds does Gateway API have and what are they?", "Four: GatewayClass, Gateway, HTTPRoute and GRPCRoute.", [(SN + "gateway.md", "Resource model", "Gateway API has four stable API kinds")], [["gatewayclass"], ["httproute"], ["grpcroute"]]),
    s("What status code does the API server return when authentication fails?", "401.", [(C + "security/controlling-access.md", "Authentication", "rejected with HTTP status code 401")], [["401"]]),
    s("Can I set two versions as the storage version of a custom resource at the same time?", "No, that is considered invalid.", [(OV + "storage-version.md", "Storage versions for custom resources", "at the same time is considered invalid")], [["invalid", "no,", "cannot"]]),
    s("What does the kubernetes.io/pv-protection finalizer prevent?", "Accidental deletion of a PersistentVolume while a Pod uses it.", [(OV + "finalizers.md", "How finalizers work", "accidental deletion of `PersistentVolume` objects")], [["deletion", "delet"], ["persistentvolume", "volume"]]),
    s("Can I add a new finalizer to an object that is pending deletion?", "No, you can remove entries but cannot add a new finalizer.", [(OV + "finalizers.md", "How finalizers work", "but you cannot add a new finalizer")], [["cannot", "can't", "no,"]]),
    s("What maximum length do list items have in compositePodGroupTemplates and podGroupTemplates?", "8 items.", [(W + "workload-api/_index.md", "Structure and constraints", "capped at a maximum of 8 items")], [["8", "eight"]]),
    s("Why do in-tree controllers set DisableDeclarativeValidation?", "The API server already runs declarative validation on the embedded blocks, so skipping avoids checking twice.", [(W + "workload-api/workloadbuilder.md", "Opting out of declarative validation", "set `DisableDeclarativeValidation`")], [["api server"], ["twice", "already"]]),
]

K8S_TR = [
    s("Bir Pod kaynak isteği LimitRange'i ihlal ederse API sunucusu hangi durum kodunu döner?", "403 Forbidden.", [(C + "policy/limit-range.md", "Constraints on resource limits and requests", "code `403 Forbidden`")], [["403"]], "tr"),
    s("cgroup v2 için en düşük Linux çekirdek sürümü nedir?", "5.8 veya sonrası.", [(AR + "cgroups.md", "Requirements", "Linux Kernel version is 5.8 or later")], [["5.8"]], "tr"),
    s("Windows üzerinde çalışan bir Pod kaç DNS sonekine sahip olabilir?", "Yalnızca 1.", [(SN + "dns-pod-service.md", "DNS resolution on Windows nodes", "you can only have 1 DNS suffix")], [["1", "bir", "one"]], "tr"),
    s("Gateway API'de kararlı kaç API türü vardır?", "Dört: GatewayClass, Gateway, HTTPRoute, GRPCRoute.", [(SN + "gateway.md", "Resource model", "Gateway API has four stable API kinds")], [["dört", "4", "four"]], "tr"),
    s("Kimlik doğrulama başarısız olursa API sunucusu hangi HTTP kodunu döner?", "401.", [(C + "security/controlling-access.md", "Authentication", "rejected with HTTP status code 401")], [["401"]], "tr"),
    s("VolumeAttributesClass en fazla kaç parametre tanımlayabilir?", "512.", [(ST + "volume-attributes-classes.md", "Parameters", "There can be at most 512 parameters")], [["512"]], "tr"),
    s("Bir Pod'un başvurduğu PodGroup henüz yoksa Pod ne olur?", "Pending durumunda kalır; PodGroup oluşunca zamanlayıcı kuyruğa alır.", [(W + "podgroup-api/lifecycle.md", "Creation ordering", "the `Pod` remains pending")], [["pending", "bekle"]], "tr"),
    s("internalTrafficPolicy varsayılan değeri nedir?", "Cluster.", [(SN + "service-traffic-policy.md", "How it works", "`Cluster` (the default)")], [["cluster"]], "tr"),
]

K8S_MULTI = [
    m("What are the nesting and list limits of the group-template hierarchy, and can I later add a new CompositePodGroupTemplate?", "Depth up to 4 levels, at most 8 items per list; you cannot add or remove CompositePodGroupTemplates later.", [(W + "workload-api/_index.md", "Structure and constraints", "capped at a maximum of 8 items"), (W + "workload-api/_index.md", "Structure and constraints", "you cannot add new or remove existing")], [["4", "four"], ["8", "eight"], ["cannot", "can't", "not"]]),
    m("Which two flags control how the HPA treats Pod readiness for CPU, and what are their defaults?", "--horizontal-pod-autoscaler-initial-readiness-delay (30 seconds) and --horizontal-pod-autoscaler-cpu-initialization-period (5 minutes).", [(W + "autoscaling/horizontal-pod-autoscale.md", "Algorithm details", "--horizontal-pod-autoscaler-initial-readiness-delay"), (W + "autoscaling/horizontal-pod-autoscale.md", "Algorithm details", "--horizontal-pod-autoscaler-cpu-initialization-period")], [["30"], ["5 min", "five min"]]),
    m("Which DNS and IP networking restrictions apply to Pods on Windows nodes?", "ClusterFirstWithHostNet is unsupported and only one DNS suffix is possible; IPv6-only is not supported.", [(SN + "dns-pod-service.md", "DNS resolution on Windows nodes", "`ClusterFirstWithHostNet` is not supported"), (SN + "dual-stack.md", "Windows support", 'does not support single-stack "IPv6-only" networking')], [["clusterfirstwithhostnet", "dns"], ["ipv6"]]),
    m("What must exist before a PodGroup can use a podGroupTemplateRef, and which scheduling policies would be copied from it?", "The referenced Workload must exist; its PodGroupTemplate's basic or gang policy is copied at creation time.", [(W + "podgroup-api/lifecycle.md", "Creation ordering", "The referenced `Workload` must exist"), (W + "podgroup-api/_index.md", "Scheduling policy", "this policy is copied from the Workload's PodGroupTemplate")], [["workload"], ["basic", "gang", "copied"]]),
    m("How does a request get rejected at authentication versus at a LimitRange check?", "Failed authentication returns 401; a LimitRange violation returns 403 Forbidden.", [(C + "security/controlling-access.md", "Authentication", "rejected with HTTP status code 401"), (C + "policy/limit-range.md", "Constraints on resource limits and requests", "code `403 Forbidden`")], [["401"], ["403"]]),
    m("Which finalizer protects a PersistentVolume, and what stops me adding more finalizers once deletion started?", "kubernetes.io/pv-protection; after a deletion timestamp is set you may remove finalizers but cannot add new ones.", [(OV + "finalizers.md", "How finalizers work", "`kubernetes.io/pv-protection`"), (OV + "finalizers.md", "How finalizers work", "but you cannot add a new finalizer")], [["pv-protection"], ["cannot", "can't", "not"]]),
    m("Which components use the Topology Manager's data and what does a device plugin send it at registration?", "The device manager consults the Topology Manager, using the TopologyInfo struct sent with device IDs and health.", [(C + "extend-kubernetes/compute-storage-net/device-plugins.md", "Device plugin integration with the Topology Manager", "The device manager will then use this information"), (C + "extend-kubernetes/compute-storage-net/device-plugins.md", "Device plugin integration with the Topology Manager", "populated TopologyInfo")], [["topologyinfo"], ["device manager", "topology manager"]]),
    m("When should a workload be a DaemonSet and which networking component is a typical example?", "When a Pod must run on all or certain hosts for node-level functionality; network plugins are a typical example.", [(W + "controllers/daemonset.md", "Deployments", "Use a DaemonSet when it is important"), (W + "controllers/daemonset.md", "Deployments", "network plugins")], [["node", "host"], ["network"]]),
    m("What limits apply to VolumeAttributesClass parameters and what is used when a parameter is omitted?", "At most 512 parameters and 256 KiB; omitted parameters use the default at provisioning.", [(ST + "volume-attributes-classes.md", "Parameters", "There can be at most 512 parameters"), (ST + "volume-attributes-classes.md", "Parameters", "the default is used at volume provisioning")], [["512"], ["default"]]),
    m("What does a kubelet need from the runtime for cgroup v2, and which CRI version does it require since 1.26?", "Runtime cgroup v2 support with the systemd cgroup driver; the v1 CRI API.", [(AR + "cgroups.md", "Requirements", "configured to use the [systemd cgroup driver]"), (C + "containers/cri.md", "The API", "supports the `v1` CRI API")], [["systemd"], ["v1"]]),
    m("Which Gateway API kinds are stable and what is the difference between internal traffic policy Local and Cluster?", "GatewayClass, Gateway, HTTPRoute, GRPCRoute; Local uses node-local endpoints, Cluster uses all endpoints.", [(SN + "gateway.md", "Resource model", "Gateway API has four stable API kinds"), (SN + "service-traffic-policy.md", "How it works", "Kubernetes considers all endpoints")], [["httproute", "gateway"], ["local"], ["all"]]),
    m("What is the difference between a VPA updater evicting and in-place updating, and where are its recommendations stored?", "It evicts Pods for recreation or updates resources in place when supported; recommendations are in .status.recommendation.", [(W + "autoscaling/vertical-pod-autoscale.md", "How does a VerticalPodAutoscaler work?", "Evict Pods, triggering their recreation"), (W + "autoscaling/vertical-pod-autoscale.md", "How does a VerticalPodAutoscaler work?", "status.recommendation")], [["evict"], ["in place", "in-place"], ["status.recommendation", "status recommendation"]]),
    m("What does the DRA list attribute limit look like and what does an admin need for a tainted device?", "48 values per device; an admin must explicitly tolerate all taints.", [(DRA + "dra-api.md", "Details for DRA Driver Authors", "is limited to **48**"), (DRA + "device-taints.md", "Device taints and tolerations", "must explicitly tolerate all taints")], [["48"], ["tolerate"]]),
    m("How do I handle stuck evictions and what happens to a Pod matching a ReplicaSet selector?", "Pause the automation or delete the Pod directly; a matching bare Pod is acquired and may be terminated.", [(SE + "api-eviction.md", "Troubleshooting stuck evictions", "Abort or pause the automated operation"), (W + "controllers/replicaset.md", "Non-Template Pod acquisitions", "they will immediately be acquired by it")], [["pause", "abort", "delete"], ["acquire"]]),
    m("Bir Service'in iç trafik politikası Local olduğunda ne olur ve varsayılan değer nedir?", "Yalnızca düğümdeki uç noktalar kullanılır; varsayılan Cluster'dır.", [(SN + "service-traffic-policy.md", "How it works", "only node local"), (SN + "service-traffic-policy.md", "How it works", "`Cluster` (the default)")], [["cluster"], ["local", "yerel", "düğüm"]], "tr"),
    m("Kimlik doğrulaması ile LimitRange reddi hangi HTTP kodlarıyla ayrılır?", "Kimlik doğrulama 401, LimitRange 403.", [(C + "security/controlling-access.md", "Authentication", "rejected with HTTP status code 401"), (C + "policy/limit-range.md", "Constraints on resource limits and requests", "code `403 Forbidden`")], [["401"], ["403"]], "tr"),
    m("Windows Pod'larında DNS soneki ve IPv6-only ağ için kısıtlar nelerdir?", "Tek DNS soneki vardır; IPv6-only desteklenmez.", [(SN + "dns-pod-service.md", "DNS resolution on Windows nodes", "you can only have 1 DNS suffix"), (SN + "dual-stack.md", "Windows support", 'does not support single-stack "IPv6-only" networking')], [["1", "tek", "bir", "one"], ["ipv6"]], "tr"),
]

K8S_NONE = [
    u("How much memory should I give the kube-apiserver for a 5000-node cluster?", "Sizing advice not in concepts.", ["apiserver memory"]),
    u("Which Helm chart installs the Cluster Autoscaler on AWS?", "Helm chart not in concepts for this.", ["cluster autoscaler helm"]),
    u("What is the monthly price of a Windows node on GKE?", "Pricing is absent.", ["per month", "monthly price"]),
    u("Which Linux distributions are officially certified for cgroup v2 by Kubernetes?", "Requirements only, no certification list.", ["certified for cgroup"]),
    u("What is the maximum number of Gateways per GatewayClass?", "No such limit documented.", ["maximum number of gateways"]),
    u("How many PodGroups can a Workload create per second?", "No rate documented.", ["podgroups per second"]),
    u("What is the default VPA update interval in seconds?", "Interval not given in the sampled concept page.", ["update interval"]),
    u("By what percentage does Memory QoS reduce OOM kills?", "No such statistic.", ["reduce oom"]),
    u("Cluster Autoscaler'ın varsayılan ölçek küçültme gecikmesi kaç dakikadır?", "Değer belgede yok.", ["scale-down-delay"], "tr"),
    u("Gateway API hangi Kubernetes sürümünde GA oldu?", "Sürüm geçmişi kavramlarda verilmez.", ["gateway api became ga"], "tr"),
    u("Kubernetes'te bir Secret'ı döndürmek (rotation) için önerilen süre kaç gündür?", "Süre önerilmez (k8s-018'in Türkçe yakını).", ["rotate every", "rotation period"], "tr"),
    u("VolumeAttributesClass'ın gcloud komutuyla oluşturulması nasıl yapılır?", "Bulut CLI'si yok.", ["gcloud"], "tr"),
    u("How long does a kubelet take to detect a new DRA device on average?", "No latency figure.", ["detect a new device"]),
    u("What is the recommended replica count for an extension API server?", "No recommendation.", ["recommended replica"]),
]

EXISTING_KEYWORDS = {
    "kvkk-001": [["otuz", "30"]],
    "kvkk-002": [["evet", "aktarılabilir"], ["yeterli önlem", "6"]],
    "kvkk-004": [["dokuz", "9"], ["türkiye büyük millet meclisi", "tbmm"], ["cumhurbaşkan"]],
    "kvkk-005": [["dört", "4"], ["yeniden seçil", "tekrar seçil", "seçilebilir"]],
    "kvkk-006": [["beş", "5"], ["iş günü"]],
    "kvkk-007": [["15.000"], ["1.000.000"]],
    "kvkk-008": [["otuz", "30"], ["altmış", "60"]],
    "kvkk-009": [["tüket", "önce", "hayır"], ["altmış", "60"], ["reddedil"]],
    "kvkk-010": [["kurul"], ["15.000"]],
    "k8s-001": [["clusterip"]],
    "k8s-002": [["restart"], ["endpointslice", "endpoint"]],
    "k8s-004": [["30000"], ["32767"]],
    "k8s-005": [["30"]],
    "k8s-006": [["25"]],
    "k8s-007": [["kube-node-lease"], ["lease", "heartbeat"]],
    "k8s-008": [["unencrypted", "not encrypted", "no,"]],
    "k8s-009": [["1 mib", "1mib"]],
    "k8s-010": [["6", "six"]],
    "k8s-011": [["never", "onfailure", "no,", "not"]],
    "k8s-012": [["headless"], ["none", "clusterip"]],
    "k8s-013": [["request", "priority"], ["besteffort", "qos"]],
    "k8s-014": [["kubernetes.io/metadata.name"]],
    "k8s-015": [["delete"]],
}
