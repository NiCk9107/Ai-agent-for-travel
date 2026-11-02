import logging
import os
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.routes_chat import router as chat_router
from api.routes_trip import router as trip_router
from db.database import DB_PATH, get_conn, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

SEED_DB = Path(__file__).parent / "data" / "seed.db"
# Собранный фронт: в Docker лежит в /app/static; локально папки нет — фронт идёт через npm run dev
STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).parent / "static")).resolve()

# Локальный фронт + адреса из переменной ALLOWED_ORIGINS (через запятую) + любые *.vercel.app
ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"] + \
          [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(title="О!дин запрос API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(trip_router, prefix="/api")


@app.on_event("startup")
def startup():
    # На сервере / в контейнере базы нет — берём стартовую из репозитория
    if not DB_PATH.exists() and SEED_DB.exists():
        shutil.copy(SEED_DB, DB_PATH)
        logging.info("База создана из data/seed.db")
    init_db()


@app.get("/health")
def health_simple():
    """Для healthcheck Docker и жюри: 200 OK, {"status": "ok"}."""
    return {"status": "ok"}


@app.get("/api/health")
def health():
    """Подробная проверка: есть ли данные и ключ модели. Открыть перед демо — «разбудит» Render."""
    with get_conn() as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("destinations", "climate", "hotels")}
    return {"ok": True, "data_ok": counts["destinations"] > 0 and counts["hotels"] > 0, **counts,
            "llm_key_set": bool(os.getenv("LLM_API_KEY")), "model": os.getenv("LLM_MODEL")}


# Фронт с того же порта 8080. Этот маршрут — ПОСЛЕДНИМ, после всех /api/...
if (STATIC_DIR / "index.html").exists():
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        file = (STATIC_DIR / path).resolve()
        if path and file.is_file() and STATIC_DIR in file.parents:
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")   # SPA: любые другие пути → index.html