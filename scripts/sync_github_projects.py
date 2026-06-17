#!/usr/bin/env python3
"""Sync public GitHub repositories into a JSON feed used by the landing page."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request


def github_get_json(url: str, token: str | None) -> Any:
    req = request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "vikipedia-sync-bot")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_homepage(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"


def has_any_homepage(repo: dict[str, Any]) -> bool:
    return normalize_homepage(repo.get("homepage")) is not None


def is_pages_homepage(url: str | None, username: str) -> bool:
    if not url:
        return False
    normalized = url.strip().lower()
    return f"{username.lower()}.github.io" in normalized


def is_github_pages_project(repo: dict[str, Any], username: str) -> bool:
    if bool(repo.get("has_pages")):
        return True
    homepage = normalize_homepage(repo.get("homepage"))
    return is_pages_homepage(homepage, username)


def is_eligible_project(repo: dict[str, Any], username: str, include_homepage_any_domain: bool) -> bool:
    if is_github_pages_project(repo, username):
        return True
    if include_homepage_any_domain and has_any_homepage(repo):
        return True
    return False


def build_project(repo: dict[str, Any], username: str) -> dict[str, Any]:
    homepage = normalize_homepage(repo.get("homepage"))
    name = repo.get("name") or ""
    pages_guess = f"https://{username}.github.io/{name}/"

    if homepage:
        url = homepage
        url_type = "homepage"
    elif repo.get("has_pages"):
        url = pages_guess
        url_type = "pages"
    else:
        url = repo.get("html_url") or f"https://github.com/{username}/{name}"
        url_type = "repo"

    topics = repo.get("topics") or []
    category = topics[0].replace("-", " ").title() if topics else "Project"

    return {
        "name": name,
        "description": (repo.get("description") or "").strip(),
        "url": url,
        "url_type": url_type,
        "repo_url": repo.get("html_url") or "",
        "language": repo.get("language") or "",
        "category": category,
        "pushed_at": repo.get("pushed_at") or "",
    }


def fetch_repositories(username: str, token: str | None) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1

    while True:
        qs = parse.urlencode({"per_page": 100, "sort": "updated", "page": page})
        url = f"https://api.github.com/users/{username}/repos?{qs}"
        batch = github_get_json(url, token)
        if not isinstance(batch, list) or not batch:
            break

        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return repos


def sync(
    username: str,
    output_path: Path,
    limit: int,
    token: str | None,
    include_homepage_any_domain: bool,
) -> int:
    repos = fetch_repositories(username, token)

    filtered = [
        repo
        for repo in repos
        if not repo.get("fork")
        and not repo.get("private")
        and not repo.get("archived")
        and repo.get("name") != f"{username}.github.io"
        and is_eligible_project(repo, username, include_homepage_any_domain)
    ]

    projects = [build_project(repo, username) for repo in filtered][:limit]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://github.com/{username}",
        "projects": projects,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(projects)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync GitHub repositories to landing page JSON feed")
    parser.add_argument("--username", default=os.getenv("GITHUB_SYNC_USERNAME", "ttoriaa"))
    parser.add_argument("--output", default="assets/github-projects.json")
    parser.add_argument("--limit", type=int, default=9)
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))
    parser.add_argument(
        "--include-homepage-any-domain",
        action="store_true",
        help=(
            "Also include repositories with any homepage URL, not only GitHub Pages. "
            "By default, only GitHub Pages projects are included."
        ),
    )
    args = parser.parse_args()

    count = sync(
        username=args.username,
        output_path=Path(args.output),
        limit=max(1, args.limit),
        token=args.token or None,
        include_homepage_any_domain=args.include_homepage_any_domain,
    )
    print(f"Synced {count} projects to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
