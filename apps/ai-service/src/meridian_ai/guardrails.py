"""Model çevresindeki kod korumaları (ADR-0016): deterministiktir, modelden önce ya da sonra çalışır.

- ``classify_request``: açıkça zararlı, istem çıkarmaya ya da kural kaldırmaya yönelik istek modele gitmez.
- ``neutralize``: belgede modele yönelmiş talimat gibi görünen paragraf bağlama girmez.
- ``UrlGuard``: cevapta yalnızca belgenin kayıtlı adresi kalır; belge metnindeki bağlantı kullanıcıya ulaşmaz.
- ``mask_pii``: kişisel veri indekse ve loglara girmez.

Kalıp listeleri kaçırır: başka sözcüklerle yazılmış saldırı geçer. Bunlar asıl güvenceyi değil, bir katmanı
oluşturur; asıl sınırlar en az yetkili araçlar, insan onayı, RLS ve kodla doğrulanan kanıttır. Ne kadarını
yakaladıkları kırmızı takım raporunda ölçülür, yanlış alarmları da gerçek korpusta sayılır.
"""

import logging
import re
import unicodedata
from collections.abc import Collection
from enum import StrEnum


class RefusalCategory(StrEnum):
    HARMFUL = "harmful"
    PROMPT_EXTRACTION = "prompt_extraction"
    JAILBREAK = "jailbreak"


_INVISIBLE = re.compile("[­​-‏‪-‮⁠-⁤﻿]")


def _normalized(text: str) -> str:
    """Görünmez karakter ve tam genişlik harflerle kalıptan kaçılamasın."""
    return _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))


_REQUEST_RULES: tuple[tuple[RefusalCategory, re.Pattern[str]], ...] = (
    (
        RefusalCategory.PROMPT_EXTRACTION,
        re.compile(
            r"(your|the|hidden)\s+system\s+(prompt|message|instructions?)"
            r"|(repeat|print|reveal|show)\b.{0,40}\b(instructions|prompt)\b"
            r"|repeat\s+everything\s+above"
            r"|sistem\s+(istem|prompt|talimat|mesaj)\w*\s*(ni|nı|nu|nü|ini|ını)?\b.{0,40}"
            r"(yaz|göster|söyle|tekrarla|paylaş|nedir)"
            r"|(talimatlarını|istemini)\s+(yaz|göster|söyle|tekrarla|paylaş)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        RefusalCategory.JAILBREAK,
        re.compile(
            r"\byou\s+are\s+now\b|\bno\s+restrictions\b|\bdeveloper\s+mode\b|\bjailbreak\b"
            r"|\bignore\s+(all\s+|your\s+|the\s+)*(previous\s+|prior\s+)*(instructions|rules)\b"
            r"|\b(kısıtlaman|kuralların?)\s+yok\b|talimatları\w*\s+(yok\s+say|görmezden\s+gel|unut)",
            re.IGNORECASE,
        ),
    ),
    (
        RefusalCategory.HARMFUL,
        # Konuyu değil üretimi hedefler: "phishing politikamız nedir?" geçerli bir sorudur.
        re.compile(
            r"\b(write|create|make|build|generate|code)\b.{0,40}"
            r"\b(ransomware|malware|keylogger|phishing|bomb|explosives?|virus)\b"
            r"|\bhow\s+to\s+(make|build)\b.{0,30}\b(bomb|explosives?|poison)\b"
            r"|\b(bomba|patlayıcı|fidye\s+yazılımı|zararlı\s+yazılım|kimlik\s+avı\s+e-?postası)\w*\b.{0,40}"
            r"(yap|yaz|oluştur|hazırla|üret)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def classify_request(text: str) -> RefusalCategory | None:
    """Reddedilecek isteğin türü; normal soruda ``None``."""
    normalized = _normalized(text)
    for category, pattern in _REQUEST_RULES:
        if pattern.search(normalized):
            return category
    return None


# Talimat çıkınca bundan kısa kalan parça kaynak değildir. Ölçümde neredeyse boş bir kaynak, modeli doğru
# belgedeki cümleyi de bulamaz ya da çevirir hale getirdi; böyle parça istemde hiç yer almaz.
MIN_RESIDUAL_CHARS = 60
_TOOL_NAMES = r"create_ticket|fetch_document|query_sql|search_knowledge"
_INSTRUCTION = re.compile(
    # Araçlara ve SQL'e doğrudan hitap: belge metninde meşru karşılığı yok denecek kadar azdır.
    rf"\b({_TOOL_NAMES})\b|\bset_config\b|\bdelete\s+from\s+core\b"
    r"|\brun\s+select\b"
    # Önceki talimatları geçersiz kılma
    r"|\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+|your\s+|these\s+)*"
    r"(previous|prior|above|earlier|preceding|instructions|text\s+above)\b"
    r"|(önceki|yukarıdaki|tüm)\s+(tüm\s+)?(talimat|kural|metin)\w*\s*(ı|i|ları|leri)?\s*"
    r"(yok\s+say|görmezden\s+gel|unut)"
    # Modele hitap ve rol değiştirme
    r"|\byou\s+are\s+now\b|\bfrom\s+now\s+on\s+you\b|\byour\s+new\s+(task|role|instructions?)\b"
    r"|\bnote\s+for\s+(agents?|assistants?|ai\b)|\b(assistant|asistan)\s*:"
    r"|\bbefore\s+answering\b|\b(every|each)\s+(answer|reply|response)\b"
    r"|\bin\s+your\s+(answer|reply|response)\b"
    r"|asıl\s+görev|sistem\s+mesajı"
    r"|\b(her\s+)?cevabın(ın)?\s+(başına|sonuna|yalnızca)|\bcevaba\b.{0,60}\bekle\b"
    r"|(?m:^\s*görev\s*:)",
    re.IGNORECASE | re.DOTALL,
)
# Büyük harf şartı: yapılandırma örneklerindeki ``system: x`` satırları talimat değildir.
_SYSTEM_SPOOF = re.compile(r"\bSYSTEM\s*:\s")
_PARAGRAPH = re.compile(r"\n\s*\n")


def is_instruction_like(text: str) -> bool:
    normalized = _normalized(text)
    return bool(_INSTRUCTION.search(normalized) or _SYSTEM_SPOOF.search(normalized))


def neutralize(text: str) -> str:
    """Talimat gibi görünen paragraflar modele gitmez; talimat cümlesi ile hedefi ayrı cümlede olabilir."""
    if not is_instruction_like(text):
        return text
    kept = [p for p in _PARAGRAPH.split(text) if not is_instruction_like(p)]
    return "\n\n".join(kept)


def carries_content(text: str) -> bool:
    """Talimat çıkarıldıktan sonra kaynak olarak kullanılacak kadar metin kaldı mı?"""
    return not is_instruction_like(text) or len(neutralize(text).strip()) >= MIN_RESIDUAL_CHARS


_URL = re.compile(r"(?:https?://|www\.)[^\s)\]>\"']+", re.IGNORECASE)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_EMPTY_LINK = re.compile(r"\[([^\]]*)\]\(\s*\)")
_REMOVED = "[bağlantı kaldırıldı]"


def strip_foreign_urls(answer: str, allowed: Collection[str]) -> str:
    """Yalnızca kayıtlı belge adresleri kalır: belge metnine yazılan adres bu listeye giremez."""

    def replace(match: re.Match[str]) -> str:
        url = match.group(0)
        return url if url.rstrip(".,;:") in allowed else _REMOVED

    without_images = _IMAGE.sub(lambda m: m.group(0) if _all_allowed(m.group(0), allowed) else "", answer)
    return _EMPTY_LINK.sub(r"\1", _URL.sub(replace, without_images).replace(f"({_REMOVED})", "()"))


def _all_allowed(text: str, allowed: Collection[str]) -> bool:
    return all(url.rstrip(".,;:") in allowed for url in _URL.findall(text))


class UrlGuard:
    """Akış için: adres parçalı gelebilir, boşluk görülene dek son sözcük bekletilir."""

    def __init__(self, allowed: Collection[str]) -> None:
        self._allowed = allowed
        self._held = ""

    def feed(self, text: str) -> str:
        self._held += text
        cut = max(self._held.rfind(" "), self._held.rfind("\n")) + 1
        ready, self._held = self._held[:cut], self._held[cut:]
        return strip_foreign_urls(ready, self._allowed) if ready else ""

    def flush(self) -> str:
        ready, self._held = self._held, ""
        return strip_foreign_urls(ready, self._allowed) if ready else ""


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
_CARD = re.compile(r"(?<![\d.-])\d(?:[ -]?\d){12,18}(?![\d-])")
_NATIONAL_ID = re.compile(r"(?<![\d.-])[1-9]\d{10}(?![\d-])")
# Başında 0 ya da +90 şart: on haneli sayılar (ör. yapılandırma değerleri) telefon sayılmaz.
_PHONE = re.compile(r"(?<![\d.])(?:\+90[ -]?|0)[2-5]\d{2}[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}(?!\d)")


def _iban_valid(value: str) -> bool:
    compact = value.replace(" ", "")
    if not 15 <= len(compact) <= 34:
        return False
    rotated = compact[4:] + compact[:4]
    return int("".join(str(int(c, 36)) for c in rotated)) % 97 == 1


def _luhn_valid(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def _national_id_valid(value: str) -> bool:
    d = [int(c) for c in value]
    return (sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10 == d[9] and sum(d[:10]) % 10 == d[10]


def mask_pii(text: str) -> str:
    """Biçimi ve sağlama toplamı tutanlar maskelenir; isim ve adres gibi biçimsiz veri yakalanamaz."""

    def checked(pattern: re.Pattern[str], valid, label: str, value: str) -> str:
        return pattern.sub(lambda m: label if valid(m.group(0)) else m.group(0), value)

    masked = _EMAIL.sub("[E-POSTA]", text)
    masked = checked(_IBAN, _iban_valid, "[IBAN]", masked)
    masked = checked(_NATIONAL_ID, _national_id_valid, "[KİMLİK-NO]", masked)
    masked = checked(_CARD, _luhn_valid, "[KART-NO]", masked)
    return _PHONE.sub("[TELEFON]", masked)


class PiiLogFilter(logging.Filter):
    """Log satırı biçimlenmeden maskelenir; istisna metni de dahil."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_pii(record.getMessage())
        record.args = None
        if record.exc_info:
            record.exc_text = mask_pii(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def install_log_masking() -> None:
    """Kök işleyicilere takılır: alt kaydedicilerden gelen satırlar da buradan geçer."""
    for handler in logging.getLogger().handlers:
        if not any(isinstance(item, PiiLogFilter) for item in handler.filters):
            handler.addFilter(PiiLogFilter())
