"""Cloud manual gate: persist only the identity hashes of *public* RSS discoveries.

The GitHub workflow supplies prior and next-state paths, but this program never
pushes Git branches, reads secrets, sends mail, or creates a schedule.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from monitor import inspect
from public_state import apply_observations, load_state, save_state


def run(config_file: Path, previous: Path, next_state: Path, evidence: Path,
        fetch=None, clock=None) -> dict:
    cfg = json.loads(config_file.read_text(encoding="utf-8"))
    prior = load_state(previous)
    now = clock or datetime.now(timezone.utc)
    if fetch is None:
        probe = inspect(cfg, now=now)
    else:
        probe = inspect(cfg, fetch=fetch, now=now)
    updated, counts = apply_observations(prior, probe, now)
    # State save only after a completed successful feed scan.
    save_state(next_state, updated)
    output = {
        "kind": "public_feed_stateful_manual_acceptance",
        "checked_at_utc": now.astimezone(timezone.utc).isoformat(),
        "sources": probe["sources"],
        "public_verified_publisher_links": probe["public_verified_publisher_links"],
        "planning_headline_matches": probe["planning_headline_matches"],
        "persistence": counts,
        "email_sent": False,
        "screenshots_sent": False,
        "scheduler_enabled": False,
        "warning": "Observed does not mean notified; state branch records public URL hashes only."
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("sources.json"))
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--next", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=Path("evidence/stateful-probe.json"))
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.previous, args.next, args.evidence),
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
