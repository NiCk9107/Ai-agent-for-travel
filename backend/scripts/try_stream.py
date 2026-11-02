import json
import sys

import httpx

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
# Локальный сервер — напрямую, мимо системного прокси/VPN; для Render — как обычно
local = "127.0.0.1" in base or "localhost" in base
client = httpx.Client(timeout=200, trust_env=not local)

resp = client.post(f"{base}/api/session")
if resp.status_code != 200 or "json" not in resp.headers.get("content-type", ""):
    sys.exit(f"❌ /api/session ответил {resp.status_code}: {resp.text[:500]}")
sid = resp.json()["session_id"]
print("🆔 сессия", sid)

body = {"session_id": sid, "message": "Хочу к морю в ноябре из Москвы, вдвоём", "action": None}
event = ""
with client.stream("POST", f"{base}/api/chat/stream", json=body) as r:
    if r.status_code != 200:
        sys.exit(f"❌ /api/chat/stream ответил {r.status_code}: {r.read().decode()[:500]}")
    for line in r.iter_lines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = json.loads(line[5:])
            if event == "status":
                print("⏳", data["text"])
            elif event == "reply":
                print("💬", data["reply"]["text"][:300])
                print("🃏", [c["type"] for c in data["reply"]["cards"]], "| этап:", data["trip"]["stage"])
            elif event == "error":
                print("❌", data)
            elif event == "done":
                print("✅ поток завершён")