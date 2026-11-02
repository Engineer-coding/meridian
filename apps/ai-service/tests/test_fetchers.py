from collections.abc import Callable

import httpx
import pytest

from meridian_ai.fetchers import GitHubFetcher
from meridian_ai.handlers import PermanentError

TREES = {
    "root": [
        {"path": "docs", "type": "tree", "sha": "t-docs"},
        {"path": "README.md", "type": "blob", "sha": "b0", "size": 10},
    ],
    "t-docs": [{"path": "en", "type": "tree", "sha": "t-en"}],
    "t-en": [
        {"path": "a.md", "type": "blob", "size": 10},
        {"path": "logo.png", "type": "blob", "size": 10},
        {"path": "sub", "type": "tree"},
        {"path": "sub/b.txt", "type": "blob", "size": 5},
        {"path": "huge.md", "type": "blob", "size": 2_000_000},
    ],
}


def github(
    overrides: dict[str, httpx.Response] | None = None, seen: list[httpx.Request] | None = None
) -> Callable[[httpx.Request], httpx.Response]:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        key = f"{request.url.host}{request.url.path}"
        if overrides and key in overrides:
            return overrides[key]
        if key == "api.github.com/repos/org/repo/commits/main":
            return httpx.Response(200, json={"sha": "c0ffee", "commit": {"tree": {"sha": "root"}}})
        if key.startswith("api.github.com/repos/org/repo/git/trees/"):
            sha = key.rsplit("/", 1)[1]
            tree = TREES[sha]
            if request.url.params.get("recursive") != "1":
                tree = [e for e in tree if "/" not in e["path"]]
            return httpx.Response(200, json={"tree": tree, "truncated": False})
        if key.startswith("raw.githubusercontent.com/org/repo/c0ffee/"):
            return httpx.Response(200, text=f"# {key.rsplit('/', 1)[1]}\n\nİçerik.")
        return httpx.Response(404)

    return handle


def fetcher(
    handler: Callable[[httpx.Request], httpx.Response], max_files: int = 100, **kwargs
) -> GitHubFetcher:
    return GitHubFetcher(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)), max_files=max_files, **kwargs
    )


async def test_text_files_under_paths_are_fetched_at_one_commit() -> None:
    docs = await fetcher(github()).fetch({"repository": "org/repo", "branch": "main", "paths": ["docs/en/"]})

    assert [d.path for d in docs] == ["docs/en/a.md", "docs/en/sub/b.txt"]
    assert {d.version for d in docs} == {"c0ffee"}
    assert docs[0].url == "https://github.com/org/repo/blob/c0ffee/docs/en/a.md"
    assert docs[0].text.startswith("# a.md")


async def test_whole_repository_when_no_paths() -> None:
    docs = await fetcher(github()).fetch({"repository": "org/repo", "branch": "main"})
    assert [d.path for d in docs] == ["README.md"]


async def test_token_is_sent_only_to_the_api() -> None:
    seen: list[httpx.Request] = []
    await fetcher(github(seen=seen), token="ghp_test").fetch(
        {"repository": "org/repo", "branch": "main", "paths": ["docs/en"]}
    )
    for request in seen:
        expected = "Bearer ghp_test" if request.url.host == "api.github.com" else None
        assert request.headers.get("Authorization") == expected


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"repository": "org/missing", "branch": "main"}, "depo veya dal bulunamadı"),
        ({"repository": "org/repo", "branch": "main", "paths": ["docs/fr"]}, "dizin bulunamadı"),
        ({"repository": "../..", "branch": "main"}, "geçersiz depo adı"),
        ({"repository": "org/repo/extra", "branch": "main"}, "geçersiz depo adı"),
    ],
)
async def test_unrecoverable_configuration_is_permanent(config: dict, message: str) -> None:
    with pytest.raises(PermanentError, match=message):
        await fetcher(github()).fetch(config)


async def test_truncated_tree_is_permanent() -> None:
    truncated = httpx.Response(200, json={"tree": [], "truncated": True})
    with pytest.raises(PermanentError, match="çok büyük"):
        await fetcher(github({"api.github.com/repos/org/repo/git/trees/root": truncated})).fetch(
            {"repository": "org/repo", "branch": "main"}
        )


async def test_file_limit_is_permanent() -> None:
    with pytest.raises(PermanentError, match="sınır 1"):
        await fetcher(github(), max_files=1).fetch(
            {"repository": "org/repo", "branch": "main", "paths": ["docs/en"]}
        )


@pytest.mark.parametrize("status", [403, 429, 502])
async def test_rate_limit_and_server_errors_are_transient(status: int) -> None:
    failing = {"api.github.com/repos/org/repo/commits/main": httpx.Response(status)}
    with pytest.raises(httpx.HTTPStatusError):
        await fetcher(github(failing)).fetch({"repository": "org/repo", "branch": "main"})
