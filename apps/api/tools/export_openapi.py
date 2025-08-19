from app.main import app
from pathlib import Path
import json

out = Path("apps/api/openapi.json")
out.write_text(json.dumps(app.openapi(), indent=2))
print(f"Wrote {out}")

