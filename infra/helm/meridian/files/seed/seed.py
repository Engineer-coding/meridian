"""Seed işi (ADR-0009): demo kiracısı, koleksiyon, kaynaklar ve izleyici üyelikleri.

Tekrar çalıştırmak güvenli.

AI servisi imajının Python'uyla çalışır (httpx ve psycopg orada). Plan SEED_PLAN ortam değişkeninde JSON:
  {"admin": "alice", "tenant": {"slug": "...", "name": "..."}, "collection": "...",
   "sources": [{"name", "repository", "branch", "paths"}], "viewers": [{"userId", "email"}],
   "timeoutSeconds": 900}

Üyelik API'de yok (yalnızca kiracıyı kuran sahip olur); izleyiciler doğrudan veritabanına yazılır.
Kullanıcı kimliği Keycloak'taki sabit kimliktir: API kullanıcıyı JWT'deki `sub` ile tanır.
"""

import hashlib
import json
import os
import sys
import time

import httpx
import psycopg

API = os.environ.get("SEED_API_URL", "http://meridian-api:8080")
TOKEN_URL = os.environ["SEED_TOKEN_URL"]
PLAN = json.loads(os.environ["SEED_PLAN"])


def idempotency_key(kind: str, name: str) -> str:
    """Oluşturma uçları Idempotency-Key ister; aynı nesne için her çalıştırmada aynı anahtar (ASCII)."""
    digest = hashlib.sha256(f"{PLAN['tenant']['slug']}/{kind}/{name}".encode()).hexdigest()[:32]
    return f"seed-{kind}-{digest}"


def log(message: str) -> None:
    print(f"seed: {message}", flush=True)


def token(username: str, password: str) -> str:
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": "meridian-dev-cli",
            "scope": "openid",
            "username": username,
            "password": password,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


class PasswordAuth(httpx.Auth):
    """Erişim token'ı kısa ömürlü (realm: 5 dk); indeksleme beklerken 401 gelince yenilenir."""

    def __init__(self, username: str, password: str) -> None:
        self._username, self._password = username, password
        self._token = token(username, password)

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code == 401:
            self._token = token(self._username, self._password)
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


def find_tenant(api: httpx.Client, slug: str) -> dict | None:
    for membership in api.get("/v1/me").raise_for_status().json()["memberships"]:
        tenant = api.get(f"/v1/tenants/{membership['tenantId']}").raise_for_status().json()
        if tenant["slug"] == slug:
            return tenant
    return None


def ensure_tenant(api: httpx.Client) -> dict:
    wanted = PLAN["tenant"]
    if tenant := find_tenant(api, wanted["slug"]):
        log(f"kiracı var: {wanted['slug']}")
        return tenant
    response = api.post(
        "/v1/tenants",
        json={"slug": wanted["slug"], "name": wanted["name"]},
        headers={"Idempotency-Key": idempotency_key("tenant", wanted["slug"])},
    )
    if response.status_code == 409:
        sys.exit(f"seed: '{wanted['slug']}' başka bir kullanıcıya ait; seed.admin o kiracının sahibi olmalı")
    log(f"kiracı oluşturuldu: {wanted['slug']}")
    return response.raise_for_status().json()


def ensure_collection(api: httpx.Client, tenant_id: str) -> str:
    name = PLAN["collection"]
    for collection in api.get(f"/v1/tenants/{tenant_id}/collections").raise_for_status().json():
        if collection["name"] == name:
            return collection["id"]
    created = api.post(
        f"/v1/tenants/{tenant_id}/collections",
        json={"name": name},
        headers={"Idempotency-Key": idempotency_key("collection", name)},
    ).raise_for_status()
    log(f"koleksiyon oluşturuldu: {name}")
    return created.json()["id"]


def list_sources(api: httpx.Client, tenant_id: str) -> list[dict]:
    sources: list[dict] = []
    cursor = None
    while True:
        params = {"cursor": cursor} if cursor else {}
        page = api.get(f"/v1/tenants/{tenant_id}/sources", params=params).raise_for_status().json()
        sources += page["items"]
        cursor = page.get("nextCursor")
        if not cursor:
            return sources


def ensure_sources(api: httpx.Client, tenant_id: str, collection_id: str) -> None:
    current = {s["name"]: s for s in list_sources(api, tenant_id)}
    existing = set(current)
    for name in {s["name"] for s in PLAN["sources"]} & existing:
        if current[name]["status"] == "failed":
            # Önceki çalıştırmadan kalan hata (ör. GitHub oran sınırı): bir kez daha kuyruğa alınır.
            api.post(f"/v1/tenants/{tenant_id}/sources/{current[name]['id']}/retry").raise_for_status()
            log(f"başarısız kaynak yeniden deneniyor: {name}")
    for source in PLAN["sources"]:
        if source["name"] in existing:
            continue
        config = {"type": "github", "repository": source["repository"]}
        if source.get("branch"):
            config["branch"] = source["branch"]
        if source.get("paths"):
            config["paths"] = source["paths"]
        body = {"name": source["name"], "collectionId": collection_id, "config": config}
        api.post(
            f"/v1/tenants/{tenant_id}/sources",
            json=body,
            headers={"Idempotency-Key": idempotency_key("source", source["name"])},
        ).raise_for_status()
        log(f"kaynak eklendi: {source['name']}")


def wait_until_ready(api: httpx.Client, tenant_id: str) -> None:
    wanted = {s["name"] for s in PLAN["sources"]}
    deadline = time.monotonic() + PLAN.get("timeoutSeconds", 900)
    while True:
        sources = [s for s in list_sources(api, tenant_id) if s["name"] in wanted]
        failed = [s for s in sources if s["status"] == "failed"]
        if failed:
            details = "; ".join(f"{s['name']}: {s.get('lastError')}" for s in failed)
            sys.exit(f"seed: indeksleme başarısız: {details}")
        if sources and all(s["status"] == "ready" for s in sources):
            log(f"{len(sources)} kaynak hazır")
            return
        if time.monotonic() > deadline:
            states = ", ".join(f"{s['name']}={s['status']}" for s in sources)
            sys.exit(f"seed: süre doldu, kaynaklar hazır değil: {states}")
        time.sleep(10)


def ensure_viewers(tenant_id: str) -> None:
    conninfo = psycopg.conninfo.make_conninfo(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    with psycopg.connect(conninfo) as db:
        for viewer in PLAN.get("viewers", []):
            db.execute(
                "INSERT INTO core.users (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                (viewer["userId"], viewer["email"]),
            )
            db.execute(
                "INSERT INTO core.memberships (tenant_id, user_id, role) VALUES (%s, %s, 'viewer')"
                " ON CONFLICT DO NOTHING",
                (tenant_id, viewer["userId"]),
            )
            log(f"izleyici üye: {viewer['email']}")


def main() -> None:
    password = os.environ["SEED_ADMIN_PASSWORD"]
    auth = PasswordAuth(PLAN["admin"], password)
    with httpx.Client(base_url=API, auth=auth, timeout=60) as api:
        tenant = ensure_tenant(api)
        collection_id = ensure_collection(api, tenant["id"])
        ensure_sources(api, tenant["id"], collection_id)
        wait_until_ready(api, tenant["id"])
    ensure_viewers(tenant["id"])
    log("tamam")


if __name__ == "__main__":
    main()
