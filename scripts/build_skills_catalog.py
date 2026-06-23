#!/usr/bin/env python3
"""Build a static skills catalog JSON from .github/skills/*/SKILL.md."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def extract_first_paragraph(markdown: str) -> str:
    lines = markdown.replace("\r", "").split("\n")
    index = 0

    if lines and lines[0].strip() == "---":
        index = 1
        while index < len(lines) and lines[index].strip() != "---":
            index += 1
        if index < len(lines):
            index += 1

    paragraph: list[str] = []
    in_code_fence = False

    for raw in lines[index:]:
        line = raw.strip()

        if line.startswith("```"):
            in_code_fence = not in_code_fence
            continue

        if in_code_fence:
            continue

        if not line:
            if paragraph:
                break
            continue

        is_non_paragraph = (
            line.startswith("#")
            or line.startswith("- ")
            or line.startswith("* ")
            or line.startswith("+ ")
            or line.startswith(">")
            or line.startswith("|")
            or bool(re.match(r"^\d+\.\s", line))
        )

        if is_non_paragraph:
            if paragraph:
                break
            continue

        paragraph.append(line)

    return " ".join(paragraph).strip()


def to_display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def iter_skill_dirs(skills_root: Path) -> Iterable[Path]:
    if not skills_root.exists():
        return []
    return sorted(p for p in skills_root.iterdir() if p.is_dir())


def build_catalog(repo_root: Path, repo_slug: str) -> dict:
    skills_root = repo_root / ".github" / "skills"
    skills = []

    for skill_dir in iter_skill_dirs(skills_root):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        slug = skill_dir.name
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
        description = extract_first_paragraph(text)
        rel_path = f".github/skills/{slug}"

        skills.append(
            {
                "slug": slug,
                "title": to_display_name(slug),
                "description": description,
                "path": rel_path,
                "url": f"https://github.com/{repo_slug}/tree/main/{rel_path}",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo_slug,
        "count": len(skills),
        "skills": skills,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build skills catalog JSON")
    parser.add_argument("--repo", required=True, help="GitHub repo slug, e.g. owner/repo")
    parser.add_argument(
        "--output",
        default="assets/skills-catalog.json",
        help="Output JSON path relative to repository root",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_catalog(repo_root, args.repo)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(f"Built skills catalog: {output_path} ({payload['count']} skills)")


if __name__ == "__main__":
    main()
