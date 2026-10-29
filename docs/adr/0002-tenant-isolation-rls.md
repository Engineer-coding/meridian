# ADR-0002: Kiracı izolasyonu — paylaşımlı şema + PostgreSQL Row Level Security

- Durum: Kabul edildi
- Tarih: 2026-10-29

## Bağlam
Meridian çok kiracılı bir SaaS'tır; kiracılar arası veri sızıntısı ürünün en ağır güvenlik
riskidir (tehdit modeli T1). Sızıntı yalnızca API cevaplarında değil, retrieval sonucunda
LLM'e giden parçalarda da olabilir — yetkisiz bir parça modele hiç ulaşmamalıdır.

Kısıtlar:
- Yüzlerce–binlerce küçük kiracı hedefleniyor (çoğu deneme/demo kiracısı).
- Tek kişilik ekip: migration ve operasyon tek seferde, tek şemada yapılabilmeli.
- Vektör ve tam metin araması da aynı izolasyon kuralına tabi olmalı (bkz. ADR-0003).
- Uygulama kodundaki tek bir eksik `WHERE tenant_id = ?` sızıntıya yol açmamalı.

## Karar
Tüm kiracılar **tek veritabanı ve tek şemayı** paylaşır. Kiracıya ait her tabloda
`tenant_id uuid NOT NULL` sütunu bulunur ve izolasyon **PostgreSQL Row Level Security**
ile veritabanı seviyesinde zorlanır. Uygulama katmanındaki filtreler ikinci savunma hattıdır,
tek savunma değildir.

Örnek politika:

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON documents
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

Her istek, işlemin başında kiracı bağlamını **işleme yerel** olarak atar:

```sql
SELECT set_config('app.tenant_id', :tenantId, true);  -- true = SET LOCAL
```

## Değerlendirilen alternatifler
| Kriter | **Paylaşımlı şema + RLS** | Kiracı başına şema | Kiracı başına veritabanı |
|---|---|---|---|
| Migration | Tek şema, tek çalıştırma | N şemada tekrar; yarım kalan migration riski | N veritabanında tekrar; orkestrasyon gerekir |
| Bağlantı havuzu | Tek havuz, verimli | `search_path` değişimi; havuz paylaşımı zorlaşır | Kiracı başına havuz; bağlantı sayısı patlar |
| 1000 kiracıda | Sorunsuz (indeksler `tenant_id` ile başlar) | Katalog şişer (1000 × tablo sayısı), `pg_dump` ve planlama yavaşlar | Operasyonel olarak pahalı; tek kişiyle yönetilemez |
| Kiracı silme | `DELETE ... WHERE tenant_id` (+ nesne depolama, indeks); test gerekir | `DROP SCHEMA` — kolay | `DROP DATABASE` — en kolay |
| İzolasyon gücü | Mantıksal; yanlış rol/ayar ile delinebilir | Mantıksal; `search_path` hatasıyla delinebilir | Fiziksel; en güçlü |
| Gürültülü komşu | Paylaşılan kaynak | Paylaşılan kaynak | Ayrılabilir |
| Kiracılar arası analitik | Kolay (yetkili rol ile) | Zor | Çok zor |

## Sonuçlar
**Olumlu**
- Uygulama kodunda unutulan bir filtre sızıntıya dönüşmez; veritabanı satırı döndürmez.
- Vektör ve tam metin sorguları da aynı politikaya tabidir; retrieval ayrıca güvence altındadır.
- Tek şema: migration, yedekleme ve izleme basit kalır.

**Bilinen tuzaklar ve önlemleri** (bunlar ihlal edilirse RLS sessizce devre dışı kalır)
1. **Tablo sahibi ve superuser RLS'i atlar.** İki ayrı rol kullanılır:
   `meridian_owner` (tabloların sahibi, yalnızca Flyway migration) ve
   `meridian_app` (çalışma zamanı; tablo sahibi değil, `NOSUPERUSER NOBYPASSRLS`).
   Ek güvence olarak tüm kiracı tablolarında `FORCE ROW LEVEL SECURITY` açıktır.
2. **`SET` değil `SET LOCAL`.** Bağlam `set_config(..., true)` ile işleme yerel atanır.
   Oturum seviyesinde `SET` kullanılırsa, bağlantı havuzunda (özellikle PgBouncer
   transaction modunda) ayar, aynı bağlantıyı alan **sonraki kiracının isteğine sızar**.
   `set_config` ayrıca bind parametresi kabul ettiği için SQL enjeksiyonuna kapalıdır.
3. **Bağlam yoksa sonuç boş olmalı.** `current_setting(..., true)` hiç atanmamışsa `NULL`,
   aynı oturumda daha önce atanmışsa boş metin döndürür. `NULLIF(..., '')` ile ikisi de
   `NULL`'a çevrilir; `tenant_id = NULL` hiçbir satırla eşleşmez (fail-closed).
4. **View'lar sahibinin yetkisiyle çalışır.** Kiracı tablolarına bakan view'lar
   `WITH (security_invoker = true)` ile tanımlanır; aksi halde RLS atlanır.
5. **Performans.** Tüm indeksler `tenant_id` ile başlar (ör. `(tenant_id, created_at)`);
   politika ifadesi basit tutulur, alt sorgu içermez.

**Doğrulama**
- Kiracı sızıntı test paketi: her uç nokta için "A kiracısı B'nin verisini göremez/değiştiremez"
  testi otomatik üretilir ve CI'da çalışır.
- Şema testi: kiracı tablosu olup RLS'i veya `FORCE`'u kapalı olan tablo varsa CI kırılır.
- Rol testi: `meridian_app` rolünün `BYPASSRLS` veya tablo sahipliği yoksa test geçer.

**Kabul edilen riskler**
- İzolasyon fiziksel değil mantıksaldır; yanlış yapılandırma tek noktadan tüm kiracıları etkiler.
  Bu risk yukarıdaki otomatik testlerle azaltılır.
- Kiracı silme çok adımlıdır (veritabanı, nesne depolama, indeksler) ve silme testiyle kanıtlanmalıdır.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Orta–yüksek.** `tenant_id` her tabloda olduğu için bir kiracıyı ayrı veritabanına taşımak
mümkündür (veri kiracı bazında dışa aktarılabilir); tüm sistemi şema/DB modeline geçirmek pahalıdır.

Tetikleyiciler:
- Bir kurumsal müşteri sözleşmeyle **fiziksel veri ayrımı** veya kendi bölgesinde barındırma isterse
  → o kiracı için ayrı veritabanı ("silo" katmanı) eklenir; diğerleri paylaşımlı kalır.
- Tek bir kiracının yükü diğerlerinin p95 gecikmesini SLO dışına iterse (gürültülü komşu).
