"""Build docs/index.html by injecting data/ JSON into template.html.

template.html stays the single source of truth for the UI and must remain
under 200 KB (project CLAUDE.md); this script fails loudly if it grows past
that. docs/ is generated output — never edit it by hand. History files under
data/history/ are not inlined; the whole data/ tree is copied to docs/data/
so the built page can fetch histories at runtime, matching the fetch
fallback paths used during development.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template.html"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
MARKER = "null; /*DATA_INJECT*/"
TEMPLATE_LIMIT_BYTES = 200_000


def load_json(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    template_size = TEMPLATE.stat().st_size
    if template_size >= TEMPLATE_LIMIT_BYTES:
        raise SystemExit(
            f"template.html is {template_size:,} bytes, at or above the "
            f"{TEMPLATE_LIMIT_BYTES:,}-byte limit. Reduce it before building."
        )

    html = TEMPLATE.read_text(encoding="utf-8")
    if html.count(MARKER) != 1:
        raise SystemExit(
            f"Expected exactly one injection marker '{MARKER}' in template.html, "
            f"found {html.count(MARKER)}."
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lens1": load_json("lens1.json"),
        "lens2": load_json("lens2.json"),
        "lens3": load_json("lens3.json"),
        "thresholds": load_json("thresholds.json"),
        # Optional: produced on demand by scripts/forward_returns.py and
        # scripts/signal_map.py respectively.
        "forward_returns": load_json("forward_returns.json")
        if (DATA_DIR / "forward_returns.json").exists() else None,
        "signal_map": load_json("signal_map.json")
        if (DATA_DIR / "signal_map.json").exists() else None,
        "lens1_calibration": load_json("lens1_calibration.json")
        if (DATA_DIR / "lens1_calibration.json").exists() else None,
    }
    # "</" is escaped so no JSON string can terminate the surrounding
    # <script> element early; "<\/" is an identical string in JSON.
    injected = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace(MARKER, injected + ";")

    DOCS_DIR.mkdir(exist_ok=True)
    output = DOCS_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    shutil.copytree(DATA_DIR, DOCS_DIR / "data", dirs_exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"template.html: {template_size:,} bytes (limit {TEMPLATE_LIMIT_BYTES:,})")
    print(f"docs/index.html: {output.stat().st_size:,} bytes")
    print("docs/data/: refreshed from data/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
