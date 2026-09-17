"""Entry point script for executing one EdgeDash cycle with CLI flags."""

import argparse
import sys

from edgedash.agents.base import AGENTS
from edgedash.config import load_config
from edgedash.orchestrator import run_cycle


def main() -> None:
    """CLI entry point for EdgeDash cycle execution."""
    parser = argparse.ArgumentParser(description="EdgeDash Autonomous Agent Execution Cycle")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print plan without executing agents or writing to DB",
    )
    parser.add_argument(
        "--force",
        action="append",
        default=[],
        help="Force agent execution even if state indicates skip (repeatable)",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print detailed SystemState breakdown and planning explanations",
    )

    args = parser.parse_args()

    # Validate forced agent names against registry & known aliases
    if args.force:
        valid_names = set(AGENTS.keys()) | {
            "fetch",
            "score",
            "analyse",
            "analyze",
            "fetcher",
            "scorer",
            "gap_analyzer",
            "gapanalyzer",
        }
        for fa in args.force:
            fa_clean = fa.strip().lower()
            if fa_clean not in valid_names:
                print(
                    f"Error: Unknown agent name '{fa}' specified in --force. Valid agents: {sorted(valid_names)}",
                    file=sys.stderr,
                )
                sys.exit(1)

    try:
        cfg = load_config()
        run_cycle(cfg, dry_run=args.dry_run, force_agents=args.force, explain=args.explain)
        sys.exit(0)
    except Exception as exc:
        print(f"Error executing cycle: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
