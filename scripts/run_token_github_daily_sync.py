#!/usr/bin/env python3
"""Daily Token sync: refresh GitHub projects feed, then rebuild personal KB artifacts.

This script updates the data sources used by Token tab:
1) assets/github-projects.json (for landing/projects context)
2) reports/knowledge_base/latest.json + latest.md + latest.html (for Token summary/content)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(step_name: str, cmd: list[str], cwd: Path) -> None:
    print(f"[token-sync] START {step_name}")
    print(f"[token-sync] CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd), check=False)
    if result.returncode != 0:
        raise SystemExit(f"[token-sync] FAIL {step_name} (exit={result.returncode})")
    print(f"[token-sync] DONE {step_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run daily GitHub -> Token tab sync")
    parser.add_argument("--username", default="ttoriaa", help="GitHub username to sync")
    parser.add_argument("--limit", type=int, default=12, help="Max projects to keep in github feed")
    parser.add_argument("--top-skills", type=int, default=12, help="Top skills to include in KB")
    parser.add_argument("--recent-limit", type=int, default=15, help="Recent file limit for KB snapshot")
    parser.add_argument(
        "--include-homepage-any-domain",
        action="store_true",
        help="Include repos with any homepage URL, not only GitHub Pages",
    )
    parser.add_argument(
        "--include-project-boards",
        action="store_true",
        help="Include GitHub Project boards when token is available",
    )
    parser.add_argument(
        "--project-board-limit",
        type=int,
        default=20,
        help="How many boards to fetch before truncation",
    )
    parser.add_argument(
        "--date",
        default="",
        help="Optional snapshot date (yyyy-mm-dd). Empty means today.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    py = str(Path(sys.executable))

    sync_cmd = [
        py,
        str(repo_root / "scripts" / "sync_github_projects.py"),
        "--username",
        args.username,
        "--output",
        "assets/github-projects.json",
        "--limit",
        str(max(1, args.limit)),
        "--project-board-limit",
        str(max(0, args.project_board_limit)),
    ]
    if args.include_homepage_any_domain:
        sync_cmd.append("--include-homepage-any-domain")
    if args.include_project_boards:
        sync_cmd.append("--include-project-boards")

    kb_cmd = [
        py,
        str(repo_root / "scripts" / "build_personal_knowledge_base.py"),
        "--top-skills",
        str(max(1, args.top_skills)),
        "--recent-limit",
        str(max(1, args.recent_limit)),
    ]
    if args.date.strip():
        kb_cmd.extend(["--date", args.date.strip()])

    run_step("sync-github-projects", sync_cmd, repo_root)
    run_step("build-personal-kb", kb_cmd, repo_root)

    print("[token-sync] SUCCESS Token tab content updated.")
    print("[token-sync] Updated files: assets/github-projects.json, reports/knowledge_base/latest.json, latest.md, latest.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
