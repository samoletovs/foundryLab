"""
Local evaluation runner for labMemoryAgent.

Reads `evals/golden.jsonl`, asks each question via the persistent agent,
scores answers against expected sources + refusal rules, and writes:

    evals/results/<timestamp>__<run_label>.json
    evals/results/<timestamp>__<run_label>.summary.md

Three metrics:
    - citation_recall : for grounded items, does the answer cite at least one
      expected_sources entry? (None expected for ungrounded items.)
    - has_citations   : for grounded items, did the model cite anything?
    - refusal_correct : for ungrounded items, does the answer contain
      "I don't know" (case-insensitive) and have zero citations?

Usage:
    python evals/run_eval.py
    python evals/run_eval.py --label after-prompt-tweak
    python evals/run_eval.py --limit 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

# Make `from src.client import ask` work when run as `python evals/run_eval.py`
EVAL_DIR = Path(__file__).resolve().parent
AGENT_DIR = EVAL_DIR.parent
sys.path.insert(0, str(AGENT_DIR / "src"))

from client import ask  # noqa: E402

GOLDEN_FILE = EVAL_DIR / "golden.jsonl"
RESULTS_DIR = EVAL_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_golden() -> list[dict]:
    items: list[dict] = []
    for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(json.loads(line))
    return items


def score_item(item: dict, answer: str, citations: list[str]) -> dict:
    """Return a per-item score record.

    Metrics for grounded items:
      - cited_expected: true if at least one citation is in expected_sources
        (file_search rarely returns ALL candidate sources, so any-hit is the
        useful signal — the strict recall fraction is reported separately for
        nuance).
      - citation_recall: hits / |expected_sources|, kept for trend tracking
      - has_citations: did the model cite anything at all
    For ungrounded:
      - refusal_correct: answer contains "I don't know" AND no citations
    """
    expected = set(item.get("expected_sources", []))
    is_grounded = item["kind"].startswith("grounded")

    cited_expected: bool | None
    citation_recall: float | None
    has_citations: bool | None
    refusal_correct: bool | None

    if is_grounded:
        if expected:
            hits = sum(1 for c in citations if c in expected)
            citation_recall = hits / len(expected)
            cited_expected = hits > 0
        else:
            citation_recall = None
            cited_expected = None
        has_citations = len(citations) > 0
        refusal_correct = None
    else:
        cited_expected = None
        citation_recall = None
        has_citations = None
        normalized = answer.lower().replace("’", "'")
        refusal_correct = "i don't know" in normalized and not citations

    return {
        "kind": item["kind"],
        "category": item.get("category"),
        "cited_expected": cited_expected,
        "citation_recall": citation_recall,
        "has_citations": has_citations,
        "refusal_correct": refusal_correct,
    }


def run(label: str, limit: int | None) -> None:
    items = load_golden()
    if limit:
        items = items[:limit]
    print(f"Running {len(items)} item(s) against the lab-memory agent...\n")

    records: list[dict] = []
    for i, item in enumerate(items, 1):
        question = item["query"]
        print(f"[{i}/{len(items)}] {question}")
        # Inter-question pause — file_search responses can be 5K-15K tokens each.
        if i > 1:
            time.sleep(20)
        t0 = time.time()
        result = ask(question)
        elapsed = time.time() - t0
        score = score_item(item, result.answer, result.citations)
        record = {
            "query": question,
            "expected_sources": item.get("expected_sources", []),
            "kind": item["kind"],
            "answer": result.answer,
            "citations": result.citations,
            "raw_status": result.raw_status,
            "error": result.error,
            "latency_seconds": round(elapsed, 1),
            "score": score,
        }
        records.append(record)
        # One-line per-question summary
        if score["citation_recall"] is not None:
            tag = f"recall={score['citation_recall']:.2f}"
        elif score["refusal_correct"] is not None:
            tag = "refused" if score["refusal_correct"] else "FAIL refusal"
        else:
            tag = "—"
        print(f"   {tag}  ({elapsed:.1f}s)\n")

    summary = summarize(records, label)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = RESULTS_DIR / f"{timestamp}__{label}"
    base.with_suffix(".json").write_text(
        json.dumps({"summary": summary, "records": records}, indent=2),
        encoding="utf-8",
    )
    md = render_markdown(summary, records, label, timestamp)
    base.with_suffix(".summary.md").write_text(md, encoding="utf-8")
    print()
    # Windows default console (cp1252) can't render unicode checkmarks.
    # Print a clean encoded version, falling back to ASCII if needed.
    try:
        print(md)
    except UnicodeEncodeError:
        print(md.encode("ascii", errors="replace").decode("ascii"))
    print(f"\nFull JSON: {base.with_suffix('.json').relative_to(AGENT_DIR.parent.parent)}")


def summarize(records: list[dict], label: str) -> dict:
    grounded_records = [r for r in records if r["kind"].startswith("grounded")]
    ungrounded_records = [r for r in records if r["kind"] == "ungrounded"]

    cited_expected = [
        bool(r["score"]["cited_expected"])
        for r in grounded_records
        if r["score"]["cited_expected"] is not None
    ]
    citation_recalls = [
        r["score"]["citation_recall"]
        for r in grounded_records
        if r["score"]["citation_recall"] is not None
    ]
    has_citations = [
        bool(r["score"]["has_citations"])
        for r in grounded_records
        if r["score"]["has_citations"] is not None
    ]
    refusals = [
        bool(r["score"]["refusal_correct"]) for r in ungrounded_records
    ]
    latencies = [r["latency_seconds"] for r in records]

    return {
        "label": label,
        "total_items": len(records),
        "grounded_items": len(grounded_records),
        "ungrounded_items": len(ungrounded_records),
        "cited_expected_rate": round(mean(cited_expected), 3) if cited_expected else None,
        "citation_recall_mean": round(mean(citation_recalls), 3) if citation_recalls else None,
        "has_citations_rate": round(mean(has_citations), 3) if has_citations else None,
        "refusal_accuracy": round(mean(refusals), 3) if refusals else None,
        "latency_seconds_mean": round(mean(latencies), 1) if latencies else None,
        "errors": sum(1 for r in records if r["error"]),
    }


def render_markdown(summary: dict, records: list[dict], label: str, ts: str) -> str:
    lines = [
        f"# Eval run — {label}",
        "",
        f"- Timestamp: `{ts}`",
        f"- Items: {summary['total_items']} ({summary['grounded_items']} grounded, {summary['ungrounded_items']} ungrounded)",
        f"- Errors: {summary['errors']}",
        f"- Mean latency: {summary['latency_seconds_mean']}s",
        "",
        "## Scores",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| cited_expected (any hit, grounded) | **{summary['cited_expected_rate']}** |",
        f"| citation_recall (mean over grounded) | **{summary['citation_recall_mean']}** |",
        f"| has_citations rate (grounded) | **{summary['has_citations_rate']}** |",
        f"| refusal_accuracy (ungrounded) | **{summary['refusal_accuracy']}** |",
        "",
        "## Per-item",
        "",
        "| # | Kind | Question | Hit / Refused | Citations |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(records, 1):
        s = r["score"]
        if s["cited_expected"] is not None:
            mark = "✓" if s["cited_expected"] else "✗"
            tag = f"{mark} {s['citation_recall']:.2f}"
        elif s["refusal_correct"] is not None:
            tag = "✓ refused" if s["refusal_correct"] else "✗ FAIL"
        else:
            tag = "—"
        cits = ", ".join(r["citations"]) if r["citations"] else "(none)"
        q = r["query"].replace("|", "\\|")
        lines.append(f"| {i} | {r['kind']} | {q} | {tag} | {cits} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline", help="run label (used in filename)")
    parser.add_argument("--limit", type=int, default=None, help="run only first N items")
    args = parser.parse_args()
    run(label=args.label, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
