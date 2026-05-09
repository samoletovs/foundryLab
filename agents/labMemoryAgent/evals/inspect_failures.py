"""Inspect failing eval items."""
import json
from pathlib import Path
results_dir = Path(__file__).resolve().parent.parent / "evals" / "results"
latest = sorted(results_dir.glob("*__path-headers.json"))[-1]
data = json.loads(latest.read_text(encoding="utf-8"))
for i in [3, 5, 7]:  # 0-indexed: items 4, 6, 8
    r = data["records"][i]
    print(f"=== Q{i+1}: {r['query']} ===")
    print(f"expected: {r['expected_sources']}")
    print(f"citations: {r['citations']}")
    print(f"score: {r['score']}")
    print("answer (first 500 chars):")
    print(r["answer"][:500])
    print()
