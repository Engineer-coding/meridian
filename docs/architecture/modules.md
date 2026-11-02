# Çekirdek API modülleri

Çekirdek API tek bir dağıtım birimidir (ADR-0001), ama içi modüllere ayrılmıştır. Her modülün
hangi modüllere bağımlı olabileceği `package-info.java` dosyasında yazılıdır ve
`ModularityTest` (Spring Modulith) bunu her derlemede denetler. İzinsiz bir bağımlılık ya da
döngü CI'ı kırar.

```mermaid
flowchart LR
    identity["Kimlik<br/><small>token → kullanıcı, kiracı kapısı, /v1/me</small>"]
    tenancy["Kiracılık<br/><small>kiracılar, üyelikler, RLS bağlamı</small>"]
    idempotency["Idempotency<br/><small>Idempotency-Key kayıtları</small>"]
    knowledge["Bilgi<br/><small>koleksiyonlar, kaynaklar</small>"]
    outbox["Outbox<br/><small>olay yazıcı + RabbitMQ aktarıcısı</small>"]
    web["Web<br/><small>ortak hata biçimi</small>"]
    contract["API sözleşmesi<br/><small>OpenAPI'den üretilir</small>"]

    identity --> tenancy
    identity --> contract
    tenancy --> idempotency
    tenancy --> contract
    knowledge --> tenancy
    knowledge --> idempotency
    knowledge --> outbox
    knowledge --> contract
```

| Modül | İzin verilen bağımlılıklar | Neden |
|---|---|---|
| `identity` | `tenancy`, `contract` | Kiracı kapısı üyeliği `tenancy`'den sorar |
| `tenancy` | `idempotency`, `contract` | Kiracı oluşturma idempotent'tir |
| `knowledge` | `tenancy`, `idempotency`, `outbox`, `contract` | Rol denetimi, tekrarlanabilir oluşturma, indeksleme olayı |
| `outbox` | — | Altyapı parçası; olayın içeriğini bilmez (ADR-0004) |
| `idempotency` | — | Altyapı parçası; iş modüllerini bilmez |
| `web` | — | Ortak HTTP davranışı; iş modüllerini bilmez |
| `contract` | — | Üretilen kod; açık modül (alt paketleri herkese görünür) |

## Modül sınırlarının ötesindeki kurallar (`ArchitectureRulesTest`)

1. **Her `@RestController` sözleşmeden üretilen bir arayüzü uygular.** Sözleşmede olmayan uç nokta yazılamaz.
2. **Ham JDBC bağlantısına yalnızca `TenantAwareTransactionManager` dokunur.** Bağlantıya doğrudan
   erişen kod kiracı bağlamını atlayabilir ya da `set_config` ile başka bir kiracıyı taklit edebilir.
3. **İstek bağlamı `ThreadLocal` ile taşınmaz.** `ScopedValue` blok bitince kendiliğinden temizlenir.

Her kural, bilerek ihlal edilerek denenmiştir (mutasyon denemesi): ihlal CI'da yakalanır.
