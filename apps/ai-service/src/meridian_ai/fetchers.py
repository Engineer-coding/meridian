"""Kaynaklardan ham belge çekme. Şimdilik yalnızca GitHub (ADR-0012)."""

import asyncio
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from meridian_ai.handlers import PermanentError

log = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".md", ".markdown", ".mdx", ".txt"}
MAX_FILE_BYTES = 1_000_000
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class RawDocument:
    path: str
    url: str
    version: str
    text: str


class Fetcher(Protocol):
    async def fetch(self, config: Mapping[str, Any]) -> list[RawDocument]: ...


class GitHubFetcher:
    """Bir deponun belirli bir dalındaki metin dosyalarını, tek bir commit'e sabitleyerek çeker.

    Sabit ana bilgisayarlara (api.github.com, raw.githubusercontent.com) gider; kiracının verdiği
    değerler yalnızca URL yolunun kodlanmış parçalarıdır, başka bir adrese istek yaptıramaz.
    Çok büyük depolarda (ör. kubernetes/website) tüm ağaç tek seferde alınamaz; ``paths``
    verilen dizinlere ağaçta adım adım inilir.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        max_files: int,
        token: str | None = None,
        concurrency: int = 8,
    ) -> None:
        self._client = client
        self._max_files = max_files
        self._headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._semaphore = asyncio.Semaphore(concurrency)

    async def fetch(self, config: Mapping[str, Any]) -> list[RawDocument]:
        repository = str(config.get("repository", ""))
        owner_repo = repository.split("/")
        if not _REPOSITORY.match(repository) or any(part in {".", ".."} for part in owner_repo):
            raise PermanentError(f"geçersiz depo adı: {repository!r}")
        branch = str(config.get("branch") or "main")
        prefixes = [p.strip("/") for p in config.get("paths") or []] or [""]

        repo = "/".join(quote(part, safe="") for part in owner_repo)
        commit = await self._api(
            f"/repos/{repo}/commits/{quote(branch, safe='')}", missing="depo veya dal bulunamadı"
        )
        sha, root_tree = commit["sha"], commit["commit"]["tree"]["sha"]

        files: dict[str, int] = {}
        for prefix in prefixes:
            tree = await self._descend(repo, root_tree, prefix)
            listing = await self._api(
                f"/repos/{repo}/git/trees/{tree}?recursive=1", missing="dizin bulunamadı"
            )
            if listing.get("truncated"):
                raise PermanentError(f"'{prefix or '/'}' çok büyük; paths ile daha küçük dizinler seçin")
            for entry in listing["tree"]:
                path = f"{prefix}/{entry['path']}" if prefix else entry["path"]
                if (
                    entry["type"] == "blob"
                    and PurePosixPath(path).suffix.lower() in TEXT_EXTENSIONS
                    and entry.get("size", 0) <= MAX_FILE_BYTES
                ):
                    files[path] = entry.get("size", 0)
        if len(files) > self._max_files:
            raise PermanentError(f"{len(files)} dosya, sınır {self._max_files}; paths ile daraltın")

        log.info("github %s@%s: %d dosya indirilecek", repository, sha[:12], len(files))
        return await asyncio.gather(*(self._raw(repo, repository, sha, path) for path in sorted(files)))

    async def _descend(self, repo: str, tree: str, prefix: str) -> str:
        for segment in filter(None, prefix.split("/")):
            listing = await self._api(f"/repos/{repo}/git/trees/{tree}", missing="dizin bulunamadı")
            match = next((e for e in listing["tree"] if e["path"] == segment and e["type"] == "tree"), None)
            if match is None:
                raise PermanentError(f"dizin bulunamadı: {prefix}")
            tree = match["sha"]
        return tree

    async def _api(self, path: str, missing: str) -> dict[str, Any]:
        response = await self._client.get(f"https://api.github.com{path}", headers=self._headers)
        if response.status_code in (404, 409, 422):
            # 409: boş depo, 422: geçersiz dal adı.
            raise PermanentError(missing)
        # 403/429 (hız sınırı) ve 5xx geçicidir; tüketici beklemeli olarak yeniden dener.
        response.raise_for_status()
        return response.json()

    async def _raw(self, repo: str, repository: str, sha: str, path: str) -> RawDocument:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        async with self._semaphore:
            response = await self._client.get(f"https://raw.githubusercontent.com/{repo}/{sha}/{encoded}")
        response.raise_for_status()
        return RawDocument(
            path=path,
            url=f"https://github.com/{repository}/blob/{sha}/{path}",
            version=sha,
            text=response.content[:MAX_FILE_BYTES].decode("utf-8", errors="replace"),
        )
