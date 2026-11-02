"""Değerlendirme korpusu (packages/eval/corpus/manifest.json): sürümü sabit, yeniden üretilebilir."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from meridian_ai.fetchers import GitHubFetcher, RawDocument

REPO_ROOT = Path(__file__).resolve().parents[5]
EVAL_DIR = REPO_ROOT / "packages" / "eval"


@dataclass(frozen=True)
class Corpus:
    id: str
    source_type: str
    version: str
    documents: list[RawDocument]


class StaticFetcher:
    """Önceden yüklenmiş belgeleri döndürür: indeksleme hattının geri kalanı üretimdekiyle aynıdır."""

    def __init__(self, documents: list[RawDocument]) -> None:
        self._documents = documents

    async def fetch(self, config: Mapping[str, Any]) -> list[RawDocument]:
        return self._documents


def manifest() -> dict[str, Any]:
    return json.loads((EVAL_DIR / "corpus" / "manifest.json").read_text(encoding="utf-8"))


async def load(cache_dir: Path, github_token: str | None = None) -> list[Corpus]:
    corpora = []
    for entry in manifest()["corpora"]:
        match entry["id"]:
            case "k8s":
                corpora.append(await _github(entry, cache_dir, github_token))
            case "kvkk":
                corpora.append(_local(entry))
            case other:
                raise ValueError(f"bilinmeyen korpus: {other}")
    return corpora


async def _github(entry: dict[str, Any], cache_dir: Path, token: str | None) -> Corpus:
    """İlk çalıştırmada GitHub'dan (sabit commit), sonra diskten; commit sabit, önbellek eskimez."""
    repository = entry["repository"].removeprefix("https://github.com/")
    cached = cache_dir / f"{entry['id']}-{entry['commit']}.json"
    if cached.exists():
        documents = [RawDocument(**d) for d in json.loads(cached.read_text(encoding="utf-8"))]
    else:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
            fetcher = GitHubFetcher(client, max_files=5_000, token=token)
            documents = await fetcher.fetch(
                {"repository": repository, "branch": entry["commit"], "paths": entry["paths"]}
            )
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps([asdict(d) for d in documents], ensure_ascii=False), encoding="utf-8")
    return Corpus(entry["id"], "github", entry["commit"], documents)


def _local(entry: dict[str, Any]) -> Corpus:
    path = EVAL_DIR / "corpus" / entry["file"]
    text = path.read_text(encoding="utf-8")
    document = RawDocument(path=entry["file"], url=entry["url"], version=entry["sha256"], text=text)
    return Corpus(entry["id"], "upload", hashlib.sha256(text.encode()).hexdigest()[:12], [document])
