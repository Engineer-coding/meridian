"""Süresi geçen demo sunucularını siler (ADR-0009). GitHub Actions'ta saatlik çalışır (.github/workflows/demo-reaper.yml).

Yalnızca `app=meridian-demo` etiketli sunuculara bakar; `expires-at` (unix saniye) geçmişse siler. Kalıcı IP'ye
(Primary IP) hiç istek atmaz: sunucu silinince IP serbest kalır ama silinmez. Etiketi bozuk sunucuya dokunmaz,
raporlar ve sıfırdan farklı kodla çıkar: biri bakmalı. Token yoksa (repo sırrı tanımlı değil) sessizce atlar.

    HCLOUD_TOKEN=... python3 infra/demo/reaper.py [--dry-run]
"""

import json
import os
import sys
import time
import urllib.request
from collections.abc import Callable, Mapping
from urllib.parse import quote

API = "https://api.hetzner.cloud/v1"
SELECTOR = "app==meridian-demo"
Transport = Callable[[str, str], dict]


def expired(servers: list[dict], now: int) -> tuple[list[dict], list[dict]]:
    """(silinecekler, etiketi bozuk olanlar)."""
    delete, broken = [], []
    for server in servers:
        raw = server.get("labels", {}).get("expires-at")
        try:
            expires_at = int(raw)
        except (TypeError, ValueError):
            broken.append(server)
            continue
        if expires_at < now:
            delete.append(server)
    return delete, broken


def http_transport(token: str) -> Transport:
    def call(method: str, path: str) -> dict:
        request = urllib.request.Request(
            API + path, method=method, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
        return json.loads(body) if body else {}

    return call


def list_servers(api: Transport) -> list[dict]:
    servers: list[dict] = []
    page: int | None = 1
    while page:
        result = api("GET", f"/servers?label_selector={quote(SELECTOR, safe='')}&page={page}")
        servers += result.get("servers", [])
        page = result.get("meta", {}).get("pagination", {}).get("next_page")
    return servers


def main(
    argv: list[str],
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
    now: int | None = None,
) -> int:
    env = os.environ if env is None else env
    dry_run = "--dry-run" in argv
    token = env.get("HCLOUD_TOKEN", "")
    if not token:
        print("reaper: token yok, atlanıyor (repo sırrı HCLOUD_TOKEN tanımlı değil)")
        return 0
    api = transport or http_transport(token)
    now = int(time.time()) if now is None else now

    delete, broken = expired(list_servers(api), now)
    for server in delete:
        if dry_run:
            print(f"reaper: silinecek (dry-run): {server['name']} (id {server['id']})")
        else:
            api("DELETE", f"/servers/{server['id']}")
            print(f"reaper: silindi: {server['name']} (id {server['id']})")
    for server in broken:
        print(f"reaper: etiketi bozuk, dokunulmadı: {server['name']} expires-at={server['labels'].get('expires-at')!r}")
    if not delete and not broken:
        print("reaper: süresi geçen demo sunucusu yok")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
