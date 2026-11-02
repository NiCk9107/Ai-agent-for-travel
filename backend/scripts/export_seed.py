import shutil
import sqlite3
from pathlib import Path

from db.database import DB_PATH

SEED = Path(__file__).parent.parent / "data" / "seed.db"

shutil.copy(DB_PATH, SEED)
conn = sqlite3.connect(SEED)
conn.executescript("DELETE FROM sessions; DELETE FROM messages; DELETE FROM orders; DELETE FROM api_cache;")
conn.commit()
conn.execute("VACUUM")
counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
          for t in ("destinations", "climate", "hotels", "rooms")}
conn.close()
print(f"✅ {SEED.name}: {SEED.stat().st_size / 1024 / 1024:.1f} МБ, {counts}")