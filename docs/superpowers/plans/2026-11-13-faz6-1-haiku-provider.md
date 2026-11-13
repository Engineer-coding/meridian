# Faz 6.1 — Haiku Sağlayıcısı Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI servisinin LLM zincirine `anthropic/<model>` sağlayıcısını eklemek ve demo modeli `claude-haiku-5-5`'i altın set ile kırmızı takım setinde ölçmek.

**Architecture:** Yeni `AnthropicLLM` sınıfı resmî `anthropic` Python SDK'sıyla (`AsyncAnthropic`) mevcut `LLM` ve `StructuredLLM` protokollerini uygular. Ayrı bir dosyada durur (`llm_anthropic.py`). `build_chain` yeni öneki tanır. Her hata ilk token'dan önce `LLMUnavailable` olur, böylece mevcut `FallbackLLM` zinciri bir sonraki sağlayıcıya geçer.

**Tech Stack:** Python 3.13, uv, `anthropic` SDK (1.x), httpx `MockTransport` (testler), pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-faz6-deployment-design.md` (bölüm "Haiku sağlayıcısı (ön adım)").

**Bu plan Faz 6'nın üç planından ilkidir.** Planların sırası:
1. Faz 6.1, Haiku sağlayıcısı (bu plan).
2. Faz 6.2, imajlar, Helm, Argo CD, yerel kind ve CI.
3. Faz 6.3, Terraform demosu, otomatik silme işi ve runbook.

6.2, 6.1'e bağlı değildir. 6.3 ise 6.2'nin üstüne kurulur.

## Global Constraints

- Model kimliği tam olarak `claude-haiku-5-5`. Tarih soneki eklenmez.
- Haiku fiyatı: girdi $0,10, çıktı $0,50 (1M token başına, 100K altı istemler).
- Bütçe: tüm gerçek ölçümler sahibinin $5'lık kredisini aşmaz; hedef $1'ın altı.
- `temperature`, `top_p` ve `top_k` gönderilmez; güncel API sürümünde bunlar 400 döner.
- Düşünme kapalıdır: `thinking={"type": "disabled"}` ve `output_config={"effort": "low"}`. Haiku 5.5 `disabled` modunu yalnızca effort `high` ya da altındayken kabul eder.
- Anahtar `ANTHROPIC_API_KEY` ortam değişkeninden okunur. Anahtar loglara, raporlara ya da hata mesajlarına yazılmaz.
- Kod yorumları ve belgeler Türkçe yazılır, commit mesajları İngilizce. Commit'ler şu satırla biter: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Raporların parmak izi (`evaluation/gate.py` içindeki `ANSWER_CODE`) `llm.py` dosyasını kapsar.
  - Görev 2'de `llm.py` değişince kayıtlı `answers*.json` ve `redteam.json` CI'da eskimiş sayılır.
  - Bu raporlar aynı görevde yenilenir.
  - Eşikler (`packages/eval/thresholds.json`) değiştirilmez.

## Review Focus

1. **Anahtar yok ya da geçersiz (401).** Servis yine açılmalı. Haiku `LLMUnavailable` olur, zincir Ollama'ya geçer; Ollama da yoksa sistem "yalnızca kaynaklar" moduna iner. Görev 1 ve Görev 2'deki testler bunu sabitler.
2. **İlk metinden önce gelen `refusal`.** Boş bir cevap dönmemeli, yedek sağlayıcıya geçilmeli. Metin geldikten sonra gelen `refusal`, akış ortasındaki hata gibi çağırana iletilir. Görev 1 sabitler.
3. **429 ya da 529 (aşırı yük).** Kullanıcı SDK'nın uzun yeniden denemelerini beklememeli. `max_retries=1` ve kısa zaman aşımıyla zincir hızlıca yedeğe geçer. Görev 1 sabitler.
4. **Birden fazla ya da baştaki `system` mesajı.** Baştaki tüm sistem mesajları API'nin üst düzey `system` alanında birleşir; mesaj listesi `user` ile başlar. Görev 1 sabitler.
5. **`max_tokens` ile kesilen cevap.** Kesilen kısım normal şekilde biter ve token sayaçları yine işlenir; sayaçsız kalırsa kota yanlış hesaplanır. Görev 1 sabitler.

---

### Task 1: `AnthropicLLM` sağlayıcısı

**Files:**
- Create: `apps/ai-service/src/meridian_ai/llm_anthropic.py`
- Create: `apps/ai-service/tests/test_llm_anthropic.py`
- Modify: `apps/ai-service/pyproject.toml` ve `uv.lock` (`uv add anthropic`)

**Interfaces:**
- Consumes: `llm.py` içinden `Message`, `LLMUnavailable` ve `usage_counter`.
- Produces:
  - `class AnthropicLLM` ve kurucusu `AnthropicLLM(client: anthropic.AsyncAnthropic, model: str)`.
  - `name` alanı `f"anthropic/{model}"` olur.
  - `async def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]`
  - `async def complete_json(self, messages: Sequence[Message], schema: dict[str, Any], *, max_tokens: int) -> str`
  - `def make_client(api_key: str, http_client: httpx.AsyncClient | None = None) -> anthropic.AsyncAnthropic`. Bu fonksiyon `max_retries=1` ve `timeout=httpx.Timeout(30.0, connect=5.0)` kullanır.

Testlerde gerçek SDK istemcisi `http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))` ile kurulur. Böylece SDK'nın kendi SSE ayrıştırması da sınanmış olur. Akış cevabı `text/event-stream` gövdesidir ve şu olayları içerir: `message_start` (`usage.input_tokens`), `content_block_start`, `content_block_delta` (`text_delta`), `content_block_stop`, `message_delta` (`stop_reason`, `usage.output_tokens`), `message_stop`. Bu fixture'ı test dosyasında `sse(*events)` yardımcısı üretir.

- [ ] **Step 1: Write the failing tests** (`tests/test_llm_anthropic.py`)

```python
async def test_streams_text_deltas_in_order():
    # deltas "Mer", "haba" -> ["Mer", "haba"]
async def test_request_has_no_sampling_params_and_disables_thinking():
    # yakalanan istek gövdesi: "temperature"/"top_p"/"top_k" yok,
    # body["thinking"] == {"type": "disabled"}, body["output_config"]["effort"] == "low",
    # body["model"] == "claude-haiku-5-5", body["max_tokens"] == 300
async def test_leading_system_messages_become_top_level_system():
    # [system "A", system "B", user "q"] -> body["system"] == "A\n\nB", body["messages"] == [{"role":"user","content":"q"}]
async def test_usage_is_added_to_the_request_counter():
    # message_start input_tokens=1200, message_delta output_tokens=80
    # -> counter.prompt_tokens == 1200, counter.completion_tokens == 80, counter.counted is True
async def test_usage_is_counted_when_cut_by_max_tokens():
    # stop_reason "max_tokens" -> akış normal biter, sayaç işlenir
@pytest.mark.parametrize("status", [401, 429, 500, 529])
async def test_http_errors_before_first_token_become_unavailable(status):
    # -> pytest.raises(LLMUnavailable); mesajda anahtar değeri geçmez
async def test_connection_error_becomes_unavailable():
async def test_refusal_before_any_text_becomes_unavailable():
    # metin yok, stop_reason "refusal" -> LLMUnavailable
async def test_refusal_after_text_raises_mid_stream():
    # "Kısmi" delta, ardından refusal -> önce "Kısmi" gelir, sonra LLMUnavailable
async def test_complete_json_sends_json_schema_format_and_returns_text():
    # body["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    # dönen değer ilk text bloğu, ör. '{"action":"finish"}'; sayaç işlenir
async def test_complete_json_refusal_becomes_unavailable():
```

Hepsi `@pytest.mark.asyncio` kullanır; projede asyncio için zaten bir ayar varsa ona uyulur, `tests/test_answering.py` buna örnektir.

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/ai-service && uv run pytest tests/test_llm_anthropic.py -q`
Expected: FAIL (`ModuleNotFoundError: meridian_ai.llm_anthropic`)

- [ ] **Step 3: `uv add anthropic` çalıştır ve `llm_anthropic.py` dosyasını yaz**

- Akış için `client.messages.stream(...)` kullanılır, metin `text_stream` üzerinden gelir. Bitişte `get_final_message()` çağrılır; `usage` ve `stop_reason` oradan okunur.
- SDK hata zinciri en dar olandan başlayarak yakalanır: `anthropic.APIStatusError` (`status_code` ile) ve `anthropic.APIConnectionError`. İkisi de `LLMUnavailable(f"{self.name}: HTTP {status}")` ya da `LLMUnavailable(f"{self.name}: {type(e).__name__}")` olur.
- `complete_json` yöntemi `messages.create(..., output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})` çağırır.
- Modül docstring'i Türkçe yazılır: veri dışarı çıkar, PII indekslemede maskelenir (ADR-0008, ADR-0016).

- [ ] **Step 4: Run to verify they pass**

Run: `cd apps/ai-service && uv run pytest tests/test_llm_anthropic.py -q && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: hepsi PASS, ruff temiz.

- [ ] **Step 5: Commit**

```bash
git add apps/ai-service/pyproject.toml apps/ai-service/uv.lock apps/ai-service/src/meridian_ai/llm_anthropic.py apps/ai-service/tests/test_llm_anthropic.py
git commit -m "feat(ai): Anthropic provider that falls back before the first token"
```

### Task 2: Zincire bağlama, ayarlar ve raporların yenilenmesi

**Files:**
- Modify: `apps/ai-service/src/meridian_ai/llm.py`. `build_chain` fonksiyonu yeni öneki tanır ve imzasına `anthropic_api_key: str = ""` eklenir.
- Modify: `apps/ai-service/src/meridian_ai/settings.py` (`anthropic_api_key: SecretStr = SecretStr("")`)
- Modify: `build_chain`'i çağıran yerler: `app.py:74`, `app.py:92`, `evaluation/__main__.py:178`, `evaluation/redteam.py:406`, `evaluation/agent_eval.py:164`. Değerlendirme komutları anahtarı `os.environ.get("ANTHROPIC_API_KEY", "")` ile okur.
- Modify: `.env.example` (boş `ANTHROPIC_API_KEY=` ve Türkçe yorum), `apps/ai-service/README.md` (ayar tablosu)
- Modify: `tests/test_answering.py` (`build_chain` testleri)
- Regenerate: `packages/eval/reports/answers.{json,md}`, `answers-bge-m3.{json,md}`, `redteam.{json,md}` (aynı model, yeni parmak izi), `apps/web/src/**/evalData.json` (`npm run gen:eval`)

**Interfaces:**
- Consumes: Task 1'deki `AnthropicLLM` ve `make_client`.
- Produces: `build_chain(spec: str, client: httpx.AsyncClient, ollama_url: str, anthropic_api_key: str = "") -> FallbackLLM`. Spec biçimi `"anthropic/claude-haiku-5-5,ollama/llama3.2:3b"`.

- [ ] **Step 1: Write the failing tests** (`tests/test_answering.py`)

```python
def test_build_chain_understands_anthropic_prefix():
    chain = build_chain("anthropic/claude-haiku-5-5, ollama/llama3.2:3b", http, "http://x", "k")
    assert chain.name == "anthropic/claude-haiku-5-5 → ollama/llama3.2:3b"
async def test_anthropic_without_key_is_unavailable_and_chain_falls_back():
    # build_chain("anthropic/claude-haiku-5-5,ollama/m", http, url, "") kurulumda hata vermez;
    # stream() Ollama sahte cevabını döner, chain.last_used == "ollama/m"
def test_build_chain_rejects_anthropic_without_model():
    # "anthropic/" -> ValueError
```

Anahtar boşsa `AnthropicLLM` istek atmadan `LLMUnavailable("anthropic/...: anahtar yok")` fırlatır. Bu kontrol kurucuya isteğe bağlı bir alan olarak eklenir, örneğin `make_client` yerine `client=None`. Kontrol Task 1'in testlerini bozmamalı.

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/ai-service && uv run pytest tests/test_answering.py -q -k build_chain`
Expected: FAIL (`desteklenmeyen LLM sağlayıcısı`)

- [ ] **Step 3: `build_chain` fonksiyonuna `case "anthropic" if model:` dalını ekle, ayarları ve çağıranları bağla**

`make_client` her `build_chain` çağrısında bir kez oluşturulur. İstemci `client` (httpx) parametresiyle paylaşılmaz; SDK kendi istemcisini yönetir.

- [ ] **Step 4: Run all ai-service tests**

Run: `make ai-test`
Expected: Yeni testler geçer. `test_committed_answer_report_is_current_and_meets_thresholds` ve `test_redteam.py::test_committed_report_is_current_and_meets_thresholds` ise "parmak izi eski" diye FAIL verir. Bu beklenen bir sonuçtur.

- [ ] **Step 5: Kayıtlı raporları aynı modelle yeniden üret**

Run:
```bash
make eval-answers NAME=answers
```
```bash
make eval-answers NAME=answers-bge-m3   # orijinal komutun bayraklarıyla; packages/eval/README.md'ye bak
```
```bash
make eval-redteam NAME=redteam
```
- Cevaplar `~/.cache/meridian/eval` içinde ad ve istemle önbellekli (20 MB mevcut). İstemler değişmediği için Ollama'ya gidilmemeli, komut dakikalar içinde bitmeli.
- Önbellek ıskası olursa (log'da Ollama çağrısı görünürse) durulur ve sahibine sorulur, çünkü CPU'da saatler sürer.
- Beklenen sonuç: skorlar, rapor içindeki eski skorlarla birebir aynı; yalnızca `fingerprint` ve tarih değişir. `git diff --stat packages/eval/reports` bunu göstermeli.

- [ ] **Step 6: Web değerlendirme verisini yenile ve tüm kapıları çalıştır**

Run: `cd apps/web && npm run gen:eval`, ardından `make ai-test` ve `make web-test`
Expected: hepsi PASS.

- [ ] **Step 7: Commit**

```bash
git add -A apps/ai-service .env.example packages/eval/reports apps/web/src
git commit -m "feat(ai): select Anthropic models in LLM_CHAIN; refresh report fingerprints"
```

### Task 3: Haiku ölçümü (sahibinin anahtarı gerekir)

Bu görev `ANTHROPIC_API_KEY` tanımlı olmadan başlamaz. Anahtar yoksa durulur ve sahibine bildirilir. Bu sırada Faz 6.2 planına geçilebilir.

**Files:**
- Create: `packages/eval/reports/answers-llama32.{json,md}` ve `redteam-llama32.{json,md}` (mevcut kanonik raporların kopyası)
- Overwrite: `packages/eval/reports/answers.{json,md}`, `redteam.{json,md}`. Bu adım yalnızca Haiku eşikleri geçerse yapılır; geçemezse kurallar aşağıda.
- Modify: `packages/eval/history.json` (önceki kanonik satır eklenir), `apps/web/scripts/gen-eval.mjs` (`current("answers", "v0.7.0 · Haiku")` ve `current("answers-llama32", "v0.6.0 · llama3.2:3b")`), `apps/web/src/**/evalData.json`
- Modify: `docs/architecture/threat-model.md` (açık sorunun yerine veri akış tablosu: Anthropic'e soru metni ve seçilen, PII'si maskelenmiş parçalar gider; kimlik, kiracı ve kullanıcı bilgisi gitmez), `CHANGELOG.md` (`[Unreleased]`), `packages/eval/README.md`

- [ ] **Step 1: Maliyeti tahmin et ve yaz**

Altın set v2'de 165 soru var ve her soru en fazla 2 çağrı yapar. Her çağrı yaklaşık 3K girdi ve 300 çıktı token'ı tutar, bu da ≈ $0,15 eder. Kırmızı takım setinin 40 senaryosu ≈ $0,05 tutar. Toplam < $0,25. Bu satır, çalıştırmadan önce sahibine gösterilir.

- [ ] **Step 2: Ölç**

Run:
```bash
make eval-answers NAME=answers-haiku LLM_CHAIN=anthropic/claude-haiku-5-5
```
```bash
make eval-redteam NAME=redteam-haiku   # --llm anthropic/claude-haiku-5-5; Makefile hedefine LLM değişkeni eklenir
```
Expected: rapor dosyaları oluşur ve özet satırı yazdırılır. Ortanca toplam süre birkaç saniye olmalı (llama3.2:3b'de 65 sn idi).

- [ ] **Step 3: Kurala göre kanonik raporu seç**

- **Kırmızı takımda `attacks_succeeded` değeri eşiği (≤ 2) aşarsa:** dur. Raporu commit'leme ve sahibine bildir; demo bunu düzeltmeden açılmaz.
- **Tüm eşikler geçerse:** mevcut kanonik raporları `*-llama32` adıyla kopyala, Haiku raporlarını `answers` ve `redteam` adlarıyla yeniden üret (önbellekten gelir, ücretsiz).
- **Yalnızca bir cevap eşiği aşılırsa:**
  - Kanonik raporlar llama raporları olarak kalır. CI kapısı kanonik raporu eşikle denetlediği için eşiği geçmeyen bir rapor kanonik yapılamaz.
  - Haiku raporu `answers-haiku` adıyla saklanır ve panelde ayrı satırda gösterilir.
  - Aşım CHANGELOG'a yazılır.
  - Bu durum spec'teki "Haiku kanonik olur" kararının bir istisnasıdır; sahibine ayrıca bildirilir.

- [ ] **Step 4: history, panel verisi ve belgeleri güncelle, kapıları çalıştır**

Run: `cd apps/web && npm run gen:eval && cd ../.. && make ai-test && make web-test`
Expected: PASS. Ardından CHANGELOG `[Unreleased]` bölümüne şu ölçüm satırları yazılır: doğru cevap oranı, gereksiz "bilmiyorum" oranı, ortanca süre ve başarılı saldırı sayısı (Haiku ile llama3.2:3b karşılaştırmalı).

- [ ] **Step 5: Commit**

```bash
git add packages/eval apps/web docs/architecture/threat-model.md CHANGELOG.md Makefile
git commit -m "docs(eval): measure Claude Haiku 5.5 on golden and red-team sets"
```
