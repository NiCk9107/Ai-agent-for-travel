import hashlib
import json
from datetime import datetime, timedelta

import httpx

from db.database import get_conn

HEADERS = {"User-Agent": "odin-zapros-hackathon/1.0"}


def _key(url: str, payload: str) -> str:
    return hashlib.sha1(f"{url}|{payload}".encode()).hexdigest()


def get_cached(key: str, ttl_days: int):
    with get_conn() as conn:
        row = conn.execute("SELECT response_json, created_at FROM api_cache WHERE key = ?",
                           (key,)).fetchone()
    if not row:
        return None
    created = datetime.fromisoformat(row["created_at"])
    if datetime.utcnow() - created > timedelta(days=ttl_days):
        return None
    return json.loads(row["response_json"])


def set_cached(key: str, data) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO api_cache (key, response_json, created_at) "
                     "VALUES (?, ?, ?)",
                     (key, json.dumps(data, ensure_ascii=False), datetime.utcnow().isoformat(" ")))


def cached_post(url: str, data: str, ttl_days: int = 30, timeout: int = 90) -> dict:
    """POST с кешем. data — тело запроса (для Overpass — текст запроса)."""
    key = _key(url, data)
    cached = get_cached(key, ttl_days)
    if cached is not None:
        return cached
    resp = httpx.post(url, data={"data": data}, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    set_cached(key, result)
    return result

def cached_get(url: str, params: dict | None = None, ttl_days: int = 30, timeout: int = 20) -> dict:
    """GET с кешем (для OSRM и других API с параметрами в адресе)."""
    key = _key(url, json.dumps(params or {}, sort_keys=True))
    cached = get_cached(key, ttl_days)
    if cached is not None:
        return cached
    resp = httpx.get(url, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    set_cached(key, result)
    return result