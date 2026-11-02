"""Sıralama metrikleri. Alaka birimi altın kaynaktır (belge + başlık), parça değil.

Bir bölüm birden çok parçaya bölünebilir; aynı kaynağın ikinci parçası yeni bilgi getirmez.
Bu yüzden her kaynak en fazla bir kez "bulunmuş" sayılır: çok parçalı bir bölüm metrikleri
şişirmez, çok kaynaklı (multi-hop) bir soru da ancak tüm kaynakları bulunduğunda tam puan alır.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Judged:
    """Bir sorunun sonuç listesi: her sıradaki parçanın karşıladığı kaynakların indeksleri."""

    relevant: Sequence[frozenset[int]]
    total_sources: int

    def first_ranks(self) -> dict[int, int]:
        """Her kaynağın ilk bulunduğu sıra (1'den başlar)."""
        ranks: dict[int, int] = {}
        for rank, sources in enumerate(self.relevant, start=1):
            for source in sources:
                ranks.setdefault(source, rank)
        return ranks


def judge(
    hits: Sequence[object], refs: Sequence[object], is_match: Callable[[object, object], bool]
) -> Judged:
    return Judged(
        relevant=[frozenset(i for i, ref in enumerate(refs) if is_match(ref, hit)) for hit in hits],
        total_sources=len(refs),
    )


def recall_at(judged: Judged, k: int) -> float:
    found = sum(1 for rank in judged.first_ranks().values() if rank <= k)
    return found / judged.total_sources


def reciprocal_rank(judged: Judged) -> float:
    ranks = judged.first_ranks().values()
    return 1.0 / min(ranks) if ranks else 0.0


def ndcg_at(judged: Judged, k: int) -> float:
    """İkili kazanç: bir sıra, henüz bulunmamış bir kaynağı ilk kez karşılıyorsa 1 kazandırır."""
    first = judged.first_ranks()
    dcg = sum(1.0 / math.log2(rank + 1) for rank in first.values() if rank <= k)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(judged.total_sources, k) + 1))
    # Tek parça iki kaynağı birden karşılayabilir; o durumda "ideal"i aşmamak için 1 ile sınırlanır.
    return min(dcg / ideal, 1.0) if ideal else 0.0
