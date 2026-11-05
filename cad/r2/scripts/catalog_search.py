"""Record public catalog evidence without dumping the catalog's global facets."""
import json
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode

root = Path(__file__).resolve().parents[1]
rows = []
for query in ("28BYJ", "28BYJ-48", "GT2 32", "GT2 150", "608", "608ZZ"):
    url = "https://api.step.parts/v1/parts?" + urlencode({"q": query, "pageSize": 3})
    try:
        with urlopen(url, timeout=15) as response:
            data = json.load(response)
        row = {"query": query, "url": url, "total": data["total"], "items": data["items"]}
    except Exception as exc:
        row = {"query": query, "url": url, "error": str(exc), "inconclusive": True}
    rows.append(row)
    print(query, row.get("total", "network error"), [i.get("id") for i in row.get("items", [])], flush=True)
(root / "reports" / "catalog_search.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
