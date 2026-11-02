"""Geçici hatalar için üstel bekleme ve jitter."""

import random
from datetime import timedelta


def backoff(attempt: int, base_ms: int, factor: int, rng: random.Random | None = None) -> timedelta:
    """``attempt``. yeniden deneme (1'den başlar) öncesi bekleme süresi.

    Üst sınır ``base * factor^(attempt-1)``; gerçek süre bunun yarısı ile tamamı arasında
    rastgele seçilir ("equal jitter"). Aynı anda düşen çok sayıda mesaj (ör. bir sağlayıcı
    kesintisi) aynı anda geri dönüp sağlayıcıyı yeniden boğmaz; en az yarı süre beklemek de
    çok kısa aralıkla tekrar denemeyi önler.
    """
    if attempt < 1:
        raise ValueError("attempt 1'den başlar")
    ceiling = base_ms * factor ** (attempt - 1)
    # Güvenlik amaçlı değil, yalnızca yük dağıtmak için rastgelelik.
    ms = (rng or random).uniform(ceiling / 2, ceiling)  # noqa: S311
    return timedelta(milliseconds=round(ms))
