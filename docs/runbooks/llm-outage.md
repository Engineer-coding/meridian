# Runbook: Model sağlayıcısı kesintisi

Alarm: `AnswersDegraded`: son 10 dakikada cevapların %10'undan fazlası model olmadan, yalnızca kaynaklarla döndü.
Tasarım: [ADR-0008](../adr/0008-llm-provider-and-fallback.md). Kullanıcı bu sırada "cevap üretilemedi, kaynaklar
aşağıda" uyarısını görür; sistem çalışmaya devam eder.

## 1. Doğrula
```promql
sum by (outcome) (increase(meridian_answers_total[10m]))
```
Loki: `{service_name="meridian-ai"} |= "LLM sağlayıcısı kullanılamıyor"`. Zincirdeki her sağlayıcı ayrı satır yazar.

## 2. Yerel model (Ollama)
```bash
curl -s http://127.0.0.1:11434/api/version
```
- Yanıt yoksa Ollama kapalıdır; yeniden başlatılır.
- Yanıt var ama model yoksa: `ollama list`; `LLM_CHAIN` içindeki model indirilmiş olmalı.
- Yanıt çok yavaşsa (CPU dolu): "Model çağrısı p95" paneli; başka ağır iş (ör. değerlendirme) aynı makinede mi?

## 3. Zincirde yedek
`LLM_CHAIN` virgülle birden çok sağlayıcı alır; ilki düşerse ikincisi ilk token'dan önce devreye girer. Yedek
tanımlı değilse kesinti süresince cevaplar bozulmuş modda kalır: bu bilinen ve kabul edilmiş bir durumdur.

## 4. Ajan
Ajan çalıştırmaları `llm_unavailable` ile biter ("Ajan çalıştırmaları" panelinde `failed`). Kullanıcı kesinti
geçince görevi yeniden başlatır; yarım kalan çalıştırma bir şey yazmamıştır.
