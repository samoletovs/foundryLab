"""
Targeted prompt optimization using observed failures from baseline eval.

Reads the latest baseline result, extracts failures (where cited_expected
is False or has_citations is False), and asks GPT-4o-mini to rewrite the
librarian prompt to address them.

Foundry's `prompt_optimize` MCP tool does roughly the same thing internally,
but doing it ourselves means we control exactly which failures drive the
rewrite (and we don't rely on the MCP tool which is having auth trouble).

Output goes to:
    config/optimized-prompt.md  (the suggested new prompt)
    config/optimization-rationale.md  (why this rewrite)

You then either accept the new prompt manually (paste into config.py) or
run `provision.py --use-optimized` to push it.

Usage:
    python evals/optimize_prompt.py
    python evals/optimize_prompt.py --baseline <results-stem>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import AzureOpenAI

# Make `from src.config import ...` work
EVAL_DIR = Path(__file__).resolve().parent
AGENT_DIR = EVAL_DIR.parent
sys.path.insert(0, str(AGENT_DIR / "src"))

from config import DEPLOYMENT, FOUNDRYLAB_DIR, INSTRUCTIONS  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"
CONFIG_DIR = AGENT_DIR / "config"

load_dotenv(FOUNDRYLAB_DIR / ".env")


def latest_baseline() -> Path:
    """Return the most recent *baseline*.json result file."""
    candidates = sorted(RESULTS_DIR.glob("*__baseline*.json"))
    if not candidates:
        raise SystemExit("No baseline result found in evals/results.")
    return candidates[-1]


def extract_failures(result_file: Path) -> list[dict]:
    """Return the records that failed citation expectations."""
    data = json.loads(result_file.read_text(encoding="utf-8"))
    failures = []
    for r in data["records"]:
        s = r["score"]
        if not r["kind"].startswith("grounded"):
            continue
        bad_citations = (
            s.get("cited_expected") is False
            or s.get("has_citations") is False
        )
        if bad_citations:
            failures.append(
                {
                    "query": r["query"],
                    "expected_sources": r["expected_sources"],
                    "actual_citations": r["citations"],
                    "answer_preview": r["answer"][:240],
                },
            )
    return failures


META_PROMPT = """You are a senior prompt engineer. You will revise a librarian
agent's system prompt so it grounds answers more reliably in retrieved files.

The agent has a `file_search` tool over a corpus of NauroLabs lab documents
(VISION.md, WORKSPACE.md, plan/ops/run reports, project READMEs, AGENTS.md
files, foundryLab learnings, etc).

Failures are CONCRETE. For each, the user query, the documents we expected
the agent to cite, what it actually cited, and a snippet of its answer is
provided.

REWRITE the system prompt so the agent:
1. ALWAYS calls file_search before answering a grounded question (failures
   show some answers came back with zero citations \u2014 that means the model
   answered from prior conversation/training instead of searching).
2. Prefers the MOST SPECIFIC matching document over a generic one. Examples:
   - For "what region is foundryLab in" prefer foundryLab/docs/learnings.md or
     foundryLab/docs/comparison.md (which contain the rationale) over
     foundryLab/README.md (which only has the result).
   - For "most recent nauro-plan report" prefer the latest .github/reports/plan/*.md
     file (date-sorted), NOT a run report.
3. Cites at least 1\u20132 source files for every grounded answer.
4. Refuses cleanly with the exact phrase "I don't know \u2014 that's not in the
   lab documents." for ungrounded questions.
5. Recognizes report types:
   - .github/reports/plan/*.md = strategic recommendations from nauro-plan
   - .github/reports/ops/*.md  = operations/cost/health from nauro-ops
   - .github/reports/run/*.md  = combined cycle output from nauro-run

Keep the tone direct and concise. Keep it under ~300 words. Return ONLY the
revised system prompt, no preamble.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=None, help="Specific baseline JSON to use")
    args = parser.parse_args()

    result_file = Path(args.baseline) if args.baseline else latest_baseline()
    print(f"Using baseline: {result_file.name}")
    failures = extract_failures(result_file)
    print(f"Found {len(failures)} grounded failure(s)")
    if not failures:
        print("Nothing to optimize \u2014 baseline is already clean. Exiting.")
        return 0

    user_payload = (
        "ORIGINAL SYSTEM PROMPT:\n```\n" + INSTRUCTIONS + "\n```\n\n"
        "OBSERVED FAILURES:\n" + json.dumps(failures, indent=2, ensure_ascii=False)
    )

    # Resolve the AOAI endpoint from the project endpoint.
    aoai_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].split("/api/")[0].replace(
        ".services.ai.azure.com", ".openai.azure.com"
    )

    cred = DefaultAzureCredential()
    token_provider = lambda: cred.get_token(  # noqa: E731
        "https://cognitiveservices.azure.com/.default"
    ).token

    client = AzureOpenAI(
        azure_endpoint=aoai_endpoint,
        api_version="2024-10-21",
        azure_ad_token_provider=token_provider,
    )

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {"role": "system", "content": META_PROMPT},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    new_prompt = response.choices[0].message.content.strip()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = CONFIG_DIR / f"optimized-prompt-{timestamp}.md"
    rationale_path = CONFIG_DIR / f"optimization-rationale-{timestamp}.md"

    out_path.write_text(new_prompt, encoding="utf-8")

    rationale = [
        f"# Prompt optimization rationale ({timestamp})",
        "",
        f"Used baseline: `{result_file.name}`",
        f"Failures considered: {len(failures)}",
        "",
        "## Failures fed to optimizer",
        "",
    ]
    for f in failures:
        rationale.append(f"### {f['query']}")
        rationale.append(f"- Expected: {', '.join(f['expected_sources']) or '(none)'}")
        rationale.append(f"- Got: {', '.join(f['actual_citations']) or '(none)'}")
        rationale.append("")
    rationale_path.write_text("\n".join(rationale), encoding="utf-8")

    print()
    print(f"New prompt written to:  {out_path.relative_to(AGENT_DIR.parent.parent)}")
    print(f"Rationale written to:   {rationale_path.relative_to(AGENT_DIR.parent.parent)}")
    print()
    print("=" * 60)
    print("OPTIMIZED PROMPT:")
    print("=" * 60)
    print(new_prompt)
    print("=" * 60)
    print()
    print("Next: review the prompt, then update src/config.py INSTRUCTIONS")
    print("      and run src/provision.py to push it, then evals/run_eval.py --label optimized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
