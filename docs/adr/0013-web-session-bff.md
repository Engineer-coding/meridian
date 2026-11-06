# ADR-0013: Web oturumu: token'lar tarayıcıya verilmez (BFF)

- Durum: Kabul edildi
- Tarih: 2026-11-06

## Bağlam
Web arayüzü Keycloak ile giriş yapıp çekirdek API'yi Bearer token ile çağırır. Arayüz, belge
içeriğinden ve model çıktısından oluşan **güvenilmez metin** gösterir (T18). Bu metinden bir XSS
çıkarsa, tarayıcı kodunun erişebildiği token çalınır ve saldırgan sayfa kapandıktan sonra da
kullanıcı adına API çağırabilir.

Cevap ayrıca SSE ile akar ve yerel modelde dakikalar sürebilir. Akış, tarayıcıdan API'ye kadar
tamponlanmadan gitmeli, kullanıcı "durdur" dediğinde bağlantı API'ye kadar kapanmalıdır.

## Karar
**Next.js sunucusu OIDC istemcisidir (Backend for Frontend). Token'lar yalnızca sunucuda okunur.**

- **Giriş:** yetkilendirme kodu + PKCE (S256) + `state`. Yönlendirme durumu kısa ömürlü şifreli bir
  çerezde durur.
- **Oturum:** erişim ve yenileme token'ı `HttpOnly`, `SameSite=Lax` (https'te `Secure`) bir çerezde,
  A256GCM ile şifreli. Anahtar `SESSION_SECRET`'tan türetilir; varsayılan değeri yoktur.
- **API vekili:** tarayıcı yalnızca aynı kökendeki `/api/v1/*` adresini çağırır. Vekil token'ı ekler,
  süresi dolmak üzereyse yeniler, gövdeyi akış olarak geçirir.
- **CSRF:** kimlik artık çerezle taşındığı için durum değiştiren her istekte `Origin` denetlenir.
- **Vekilin sınırları:** yalnızca `/v1` altı; `..` reddedilir. Çerez ve istemcinin `Authorization`
  başlığı API'ye geçmez; `Set-Cookie` tarayıcıya dönmez.
- **Akış:** `compress: false` ve `X-Accel-Buffering: no`. İstek iptali API'ye kadar taşınır.
- **Çıkış:** yalnızca POST. Keycloak oturumu yenileme token'ıyla arka kanaldan kapatılır.
- **CSP:** her istekte nonce; `connect-src 'self'`, dış görsel yok. Sanitizer delinse bile enjekte edilen
  betik çalışmaz, veri dışarı taşınamaz.

## Değerlendirilen alternatifler
| Seçenek | Artıları | Eksileri |
|---|---|---|
| **BFF + şifreli çerez** | XSS token çalamaz; CORS gerekmez; API değişmez | Her istek Next'ten geçer; çerez 4 KB ile sınırlı; CSRF denetimi gerekir |
| Tarayıcıda PKCE (token bellekte) | Basit, vekil yok | XSS token'ı okuyabilir; API'de CORS gerekir |
| Auth.js | Hazır çözüm | Kod akışının ve yenilemenin ayrıntıları gizlenir; ihtiyaç üç kısa uç nokta |
| Redis'te sunucu oturumu | Çerez küçük; anında iptal | Web katmanına yeni bir bağımlılık; şimdilik gerekmiyor |

## Sonuçlar
**Olumlu**
- XSS'in etkisi "sayfa açıkken" ile sınırlı; oturum dışarı taşınamaz.
- API güvenlik modeli değişmedi: durumsuz, yalnızca Bearer token kabul eder.

**Olumsuz / kabul edilen riskler**
- Çerez boyutu token boyutuna bağlı. 4 KB'yi aşan çerez tarayıcı tarafından sessizce atılıp giriş
  döngüsüne yol açacağı için `seal` bu durumda açık hata verir.
- Çıkış yapılmadan çalınan bir çerez, süresi dolana kadar geçerlidir (8 saat).
- `style-src 'unsafe-inline'` kaldı: atıf penceresinin konumu satır içi stil kullanıyor.
- Yeniden bağlanma (`Last-Event-ID`) yok: API olayları saklamıyor. Bağlantı koparsa kullanıcı
  yeniden sorar; kesilen cevap `interrupted` kaydedilir.

## Geri dönüş maliyeti ve yeniden değerlendirme tetikleyicisi
**Orta.** Oturum ve vekil dört dosyadadır; tarayıcı kodu yalnızca `/api` adresini bilir.

Tetikleyiciler:
- Gerçek token'la çerez 4 KB'ye yaklaşırsa ya da anında oturum iptali gerekirse: Redis oturumu.
- Vekil, yük testinde (Faz 5) darboğaz çıkarsa: aynı kökende ters vekille doğrudan API'ye yönlendirme.
