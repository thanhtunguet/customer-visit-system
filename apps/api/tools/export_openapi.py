import sys

sys.path.append(".")
import json
from pathlib import Path

from app.main import app

out = Path("openapi.json")
out.write_text(json.dumps(app.openapi(), indent=2))
print(f"Wrote {out}")
