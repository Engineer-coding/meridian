"""reaper.py: yalnızca süresi geçmiş demo sunucuları silinir; kalıcı IP'ye asla dokunulmaz."""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reaper  # noqa: E402


def server(id_: int, expires: str | None) -> dict:
    labels = {"app": "meridian-demo"}
    if expires is not None:
        labels["expires-at"] = expires
    return {"id": id_, "name": f"s{id_}", "labels": labels}


class FakeApi:
    def __init__(self, servers: list[dict]) -> None:
        self.servers = servers
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str) -> dict:
        self.calls.append((method, path))
        if method == "GET":
            return {"servers": self.servers, "meta": {"pagination": {"next_page": None}}}
        return {}


def run(api: FakeApi, *args: str, token: str = "t", now: int = 200) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = reaper.main(list(args), transport=api, env={"HCLOUD_TOKEN": token} if token else {}, now=now)
    return code, out.getvalue()


class ExpiredTest(unittest.TestCase):
    def test_selects_only_expired_demo_servers(self) -> None:
        delete, broken = reaper.expired([server(1, "100"), server(2, "300")], now=200)
        self.assertEqual([s["id"] for s in delete], [1])
        self.assertEqual(broken, [])

    def test_reports_but_keeps_servers_with_a_bad_label(self) -> None:
        delete, broken = reaper.expired([server(1, "yarın"), server(2, None)], now=200)
        self.assertEqual(delete, [])
        self.assertEqual([s["id"] for s in broken], [1, 2])


class MainTest(unittest.TestCase):
    def test_dry_run_deletes_nothing(self) -> None:
        api = FakeApi([server(1, "100")])
        code, out = run(api, "--dry-run")
        self.assertEqual(code, 0)
        self.assertNotIn("DELETE", [m for m, _ in api.calls])
        self.assertIn("s1", out)

    def test_deletes_with_the_label_selector_and_never_touches_primary_ips(self) -> None:
        api = FakeApi([server(1, "100"), server(2, "300")])
        code, _ = run(api)
        self.assertEqual(code, 0)
        self.assertEqual(api.calls[0], ("GET", "/servers?label_selector=app%3D%3Dmeridian-demo&page=1"))
        self.assertIn(("DELETE", "/servers/1"), api.calls)
        self.assertNotIn(("DELETE", "/servers/2"), api.calls)
        self.assertFalse(any("primary_ips" in path for _, path in api.calls))

    def test_exits_cleanly_without_a_token(self) -> None:
        api = FakeApi([server(1, "100")])
        code, out = run(api, token="")
        self.assertEqual(code, 0)
        self.assertIn("token yok", out)
        self.assertEqual(api.calls, [])

    def test_fails_when_a_label_is_broken_so_someone_looks(self) -> None:
        api = FakeApi([server(1, "yarın")])
        code, out = run(api)
        self.assertEqual(code, 1)
        self.assertIn("s1", out)
        self.assertNotIn(("DELETE", "/servers/1"), api.calls)


if __name__ == "__main__":
    unittest.main()
