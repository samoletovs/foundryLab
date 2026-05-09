"""
CLI for labMemoryAgent.

Usage:
    python src/ask.py "Why does foundryLab exist?"
    python src/ask.py --json "What is rosette?"
"""
from __future__ import annotations

import argparse
import json
import sys

from client import ask


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ask the NauroLabs lab-memory agent a question.",
    )
    parser.add_argument("question", help="The question to ask.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable output.",
    )
    args = parser.parse_args()

    result = ask(args.question)

    if args.json:
        print(
            json.dumps(
                {
                    "answer": result.answer,
                    "citations": result.citations,
                    "status": result.raw_status,
                    "error": result.error,
                },
                indent=2,
            ),
        )
    else:
        if result.error:
            print(f"ERROR: {result.error}", file=sys.stderr)
            return 1
        print(result.answer)
        if result.citations:
            print()
            print("Sources:")
            for c in result.citations:
                # Filenames were uploaded as path__separated__form
                pretty = c.replace("__", "/")
                print(f"  - {pretty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
