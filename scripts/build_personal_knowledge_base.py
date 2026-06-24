#!/usr/bin/env python3
"""Build a personal/project knowledge base snapshot from workspace artifacts.

This script creates:
- reports/knowledge_base/<date>/personal_kb.md
- reports/knowledge_base/<date>/personal_kb.json
- reports/knowledge_base/latest.md
- reports/knowledge_base/index.html
- reports/knowledge_base/latest.html
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FileNote:
    path: str
    updated_at: str
    preview: str = ""


def read_first_non_empty_line(file_path: Path, max_lines: int = 60) -> str:
    if not file_path.exists() or not file_path.is_file():
        return ""
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for idx, line in enumerate(handle):
                if idx >= max_lines:
                    break
                text = line.strip()
                if text:
                    return text
    except OSError:
        return ""
    return ""


def format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def collect_recent_files(root: Path, pattern: str, limit: int, include_preview: bool) -> list[FileNote]:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    output: list[FileNote] = []

    for item in files:
        if not item.is_file():
            continue
        preview = read_first_non_empty_line(item) if include_preview else ""
        output.append(
            FileNote(
                path=item.as_posix(),
                updated_at=format_ts(item.stat().st_mtime),
                preview=preview,
            )
        )
        if len(output) >= limit:
            break

    return output


def load_skills_catalog(repo_root: Path) -> tuple[int, list[dict[str, Any]]]:
    catalog_path = repo_root / "assets" / "skills-catalog.json"
    if catalog_path.exists():
        try:
            payload = json.loads(catalog_path.read_text(encoding="utf-8", errors="ignore"))
            skills = payload.get("skills", [])
            if isinstance(skills, list):
                return int(payload.get("count", len(skills))), skills
        except json.JSONDecodeError:
            pass

    skill_dirs = sorted((repo_root / ".github" / "skills").glob("*/SKILL.md"))
    skills: list[dict[str, Any]] = []
    for skill_md in skill_dirs:
        slug = skill_md.parent.name
        skills.append(
            {
                "slug": slug,
                "path": skill_md.relative_to(repo_root).as_posix(),
                "description": read_first_non_empty_line(skill_md),
            }
        )
    return len(skills), skills


def load_github_projects_feed(repo_root: Path, top_n: int = 5) -> dict[str, Any]:
    feed_path = repo_root / "assets" / "github-projects.json"
    if not feed_path.exists():
        return {"count": 0, "generated_at": "", "source": "", "top_projects": []}

    try:
        payload = json.loads(feed_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {"count": 0, "generated_at": "", "source": "", "top_projects": []}

    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        projects = []

    top_projects: list[dict[str, Any]] = []
    for item in projects[:top_n]:
        if not isinstance(item, dict):
            continue
        top_projects.append(
            {
                "name": item.get("name", "Unknown Project"),
                "url": item.get("url", ""),
                "pushed_at": item.get("pushed_at", ""),
                "url_type": item.get("url_type", ""),
            }
        )

    return {
        "count": len(projects),
        "generated_at": str(payload.get("generated_at", "")),
        "source": str(payload.get("source", "")),
        "top_projects": top_projects,
    }


def count_html_pages(repo_root: Path) -> dict[str, int]:
    root_html = len([p for p in repo_root.glob("*.html") if p.is_file()])
    site_html = len([p for p in (repo_root / "site").glob("**/*.html") if p.is_file()])
    return {"root_html": root_html, "site_html": site_html}


def to_rel(repo_root: Path, absolute_path: str) -> str:
    path = Path(absolute_path)
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _collect_prefix_counts(items: list[dict[str, Any]], depth: int = 2) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for item in items:
        raw = str(item.get("path", "")).strip("/")
        if not raw:
            continue
        parts = [part for part in raw.split("/") if part]
        if not parts:
            continue
        key = "/".join(parts[:depth])
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)


def build_auto_summary(payload: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    website_recent = payload.get("website", {}).get("recent_pages", [])
    dongchedi_reports = payload.get("reports", {}).get("dongchedi_summary_md", [])
    brief_reports = payload.get("reports", {}).get("daily_brief_and_news_md", [])
    task_logs = payload.get("task_logs", [])
    github_projects = payload.get("github_projects", {})

    top_website_prefix = _collect_prefix_counts(website_recent, depth=2)
    top_report_prefix = _collect_prefix_counts(dongchedi_reports + brief_reports, depth=3)

    overview_en = [
        (
            f"Snapshot covers {payload['skills']['count']} tracked skills, "
            f"{payload['website']['root_html']} root HTML pages, and {payload['website']['site_html']} site HTML pages."
        ),
        (
            f"Evidence pool includes {len(dongchedi_reports)} Dongchedi summaries, "
            f"{len(brief_reports)} daily brief/news files, and {len(task_logs)} recent task logs."
        ),
        f"GitHub landing feed currently tracks {github_projects.get('count', 0)} projects for Token/landing updates.",
        f"Decision memory currently contains {len(decisions)} recent structured entries.",
    ]
    overview_zh = [
        (
            f"当前快照覆盖 {payload['skills']['count']} 个技能条目、"
            f"{payload['website']['root_html']} 个根目录 HTML 页面，以及 {payload['website']['site_html']} 个 site HTML 页面。"
        ),
        (
            f"证据池包含 {len(dongchedi_reports)} 份懂车帝日报、"
            f"{len(brief_reports)} 份 daily brief/news 文件，以及 {len(task_logs)} 份近期任务日志。"
        ),
        f"GitHub landing feed 当前跟踪 {github_projects.get('count', 0)} 个项目，可用于 Token/landing 更新。",
        f"决策记忆当前包含 {len(decisions)} 条结构化记录。",
    ]

    patterns_en: list[str] = []
    patterns_zh: list[str] = []
    if top_website_prefix:
        patterns_en.append(
            f"Website updates are concentrated in {top_website_prefix[0][0]} ({top_website_prefix[0][1]} files in recent snapshot)."
        )
        patterns_zh.append(
            f"网站更新主要集中在 {top_website_prefix[0][0]}（近期快照中 {top_website_prefix[0][1]} 个文件）。"
        )
    if top_report_prefix:
        patterns_en.append(
            f"Reporting activity clusters around {top_report_prefix[0][0]} ({top_report_prefix[0][1]} files in recent snapshot)."
        )
        patterns_zh.append(
            f"报告活动主要集中在 {top_report_prefix[0][0]}（近期快照中 {top_report_prefix[0][1]} 个文件）。"
        )
    if len(task_logs) >= 8:
        patterns_en.append("Task execution cadence is stable: logs show repeated automated runs rather than sporadic manual-only updates.")
        patterns_zh.append("任务执行节奏较稳定：日志显示为连续自动运行，而不是零散人工更新。")
    else:
        patterns_en.append("Task execution records are present but still sparse; cadence confidence is moderate.")
        patterns_zh.append("任务执行记录已存在但仍偏少，节奏稳定性判断为中等。")

    lessons_en: list[str] = [
        "Keeping decision logs in JSONL materially improves traceability from action to rationale.",
        "A stable latest.md/latest.html entry point reduces retrieval friction for both humans and downstream automations.",
    ]
    lessons_zh: list[str] = [
        "将决策日志沉淀为 JSONL，可以显著提升从动作到原因的可追溯性。",
        "稳定的 latest.md/latest.html 入口能明显降低人和自动化流程的检索成本。",
    ]
    if decisions:
        latest = decisions[0]
        latest_title = str(latest.get("title", "")).strip()
        if latest_title:
            lessons_en.append(f"Recent focus indicates compounding value from automation-first setup: {latest_title}.")
            lessons_zh.append(f"近期重点显示自动化优先的复利价值在增强：{latest_title}。")

    next_actions_en = [
        "After each major run, add one decision entry with objective, chosen option, and expected impact.",
        "Keep daily summary generation running so trend-level signals remain visible in weekly reviews.",
        "Promote one weekly synthesis note from records to reusable playbook guidance.",
    ]
    next_actions_zh = [
        "每次关键执行后补一条决策记录，包含目标、选项与预期影响。",
        "持续保持日报生成，让周度复盘可见趋势级信号。",
        "每周从记录中提炼一条综合总结，沉淀为可复用 playbook。",
    ]

    return {
        "en": {
            "overview": overview_en,
            "patterns": patterns_en,
            "lessons": lessons_en,
            "next_actions": next_actions_en,
        },
        "zh": {
            "overview": overview_zh,
            "patterns": patterns_zh,
            "lessons": lessons_zh,
            "next_actions": next_actions_zh,
        },
    }


def build_markdown(payload: dict[str, Any], summary: dict[str, dict[str, list[str]]]) -> str:
    summary_en = summary.get("en", {})
    lines: list[str] = []
    lines.append("# Personal Knowledge Base Snapshot")
    lines.append("")
    lines.append(f"- Generated at: {payload['generated_at']}")
    lines.append(f"- Workspace: {payload['workspace_name']}")
    lines.append("")

    lines.append("## 1) What This Captures")
    lines.append("")
    lines.append("- Chat and thinking are captured as decision summaries and execution evidence, not hidden internal chain-of-thought.")
    lines.append("- Website building process from generated pages and report artifacts.")
    lines.append("- Skill training process from skill definitions and run outputs.")
    lines.append("- Task execution evidence from healthcheck/task logs.")
    lines.append("")

    lines.append("## 2) Skill Training Snapshot")
    lines.append("")
    lines.append(f"- Skill count: {payload['skills']['count']}")
    for skill in payload["skills"]["top_skills"]:
        lines.append(f"- {skill.get('slug', 'unknown')}: {skill.get('description', '')}")
    lines.append("")

    lines.append("## 3) Website Build Snapshot")
    lines.append("")
    lines.append(f"- Root html pages: {payload['website']['root_html']}")
    lines.append(f"- Site html pages: {payload['website']['site_html']}")
    for item in payload["website"]["recent_pages"]:
        lines.append(f"- {item['path']} (updated: {item['updated_at']})")
    lines.append("")

    lines.append("## 4) Pipeline and Reports Snapshot")
    lines.append("")
    lines.append("### Recent Dongchedi Daily Summaries")
    for item in payload["reports"]["dongchedi_summary_md"]:
        lines.append(f"- {item['path']} (updated: {item['updated_at']})")
    lines.append("")

    lines.append("### Recent Daily Brief / Daily News")
    for item in payload["reports"]["daily_brief_and_news_md"]:
        lines.append(f"- {item['path']} (updated: {item['updated_at']})")
    lines.append("")

    lines.append("### GitHub Projects Feed")
    lines.append(f"- Project count: {payload['github_projects']['count']}")
    if payload["github_projects"].get("generated_at"):
        lines.append(f"- Feed generated at: {payload['github_projects']['generated_at']}")
    for project in payload["github_projects"]["top_projects"]:
        pushed = f" (pushed: {project.get('pushed_at', '')})" if project.get("pushed_at") else ""
        lines.append(f"- {project.get('name', 'Unknown')}: {project.get('url', '')}{pushed}")
    lines.append("")

    lines.append("## 5) Task Execution Evidence")
    lines.append("")
    for item in payload["task_logs"]:
        preview = f" | {item['preview']}" if item.get("preview") else ""
        lines.append(f"- {item['path']} (updated: {item['updated_at']}){preview}")
    lines.append("")

    lines.append("## 6) Suggested Knowledge Workflow")
    lines.append("")
    lines.append("- Step A: Keep using the existing daily pipelines; they already generate stable evidence in reports/.")
    lines.append("- Step B: After each important chat or implementation, add a short decision note under reports/knowledge_base/notes/.")
    lines.append("- Step C: Run this script daily or after major changes to refresh the snapshot.")
    lines.append("- Step D: Publish snapshot to Confluence/Feishu if needed.")
    lines.append("")

    lines.append("## 7) Auto Summary and Lessons")
    lines.append("")

    lines.append("### Overview")
    for item in summary_en.get("overview", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Patterns Observed")
    for item in summary_en.get("patterns", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Experience and Lessons")
    for item in summary_en.get("lessons", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Next Actions")
    for item in summary_en.get("next_actions", []):
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def load_recent_decisions(repo_root: Path, limit: int = 20) -> list[dict[str, Any]]:
    index_path = repo_root / "reports" / "knowledge_base" / "notes" / "decision_log.jsonl"
    if not index_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    try:
        with index_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except OSError:
        return []

    rows.sort(key=lambda item: (str(item.get("date", "")), str(item.get("time", ""))), reverse=True)
    return rows[:limit]


def build_html(
    payload: dict[str, Any],
    decisions: list[dict[str, Any]],
    summary: dict[str, dict[str, list[str]]],
    lang: str = "en",
) -> str:
    def safe(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    is_zh = lang == "zh"
    summary_lang = summary.get("zh", {}) if is_zh else summary.get("en", {})

    title_page = "个人知识库" if is_zh else "Personal Knowledge Base"
    title_skill = "技能快照" if is_zh else "Skill Snapshot"
    title_github = "GitHub 项目更新" if is_zh else "GitHub Project Updates"
    title_decision = "近期决策" if is_zh else "Recent Decisions"
    title_website = "网站构建快照" if is_zh else "Website Build Snapshot"
    title_dongchedi = "懂车帝日报" if is_zh else "Dongchedi Daily Summaries"
    title_news = "Daily Brief 与新闻" if is_zh else "Daily Brief and News"
    title_task = "任务执行证据" if is_zh else "Task Execution Evidence"
    title_quick = "快速链接" if is_zh else "Quick Links"
    title_summary = "自动总结与经验" if is_zh else "Auto Summary and Experience"
    latest_md_text = "最新快照 latest.md" if is_zh else "latest.md"
    today_md_text = "今日 personal_kb.md" if is_zh else "today personal_kb.md"
    notes_text = "决策笔记目录" if is_zh else "decision notes folder"
    github_empty_text = "GitHub feed 暂无项目。" if is_zh else "No GitHub projects in feed yet."
    decision_empty_text = "暂无决策日志。" if is_zh else "No decision logs yet."
    label_generated_at = "生成时间" if is_zh else "Generated at"
    label_workspace = "工作区" if is_zh else "Workspace"
    label_skills = "技能数" if is_zh else "Skills"
    label_root_html = "根目录页面" if is_zh else "Root html"
    label_site_html = "站点页面" if is_zh else "Site html"

    skill_items = "".join(
        f"<li><strong>{safe(skill.get('slug', 'unknown'))}</strong>: {safe(skill.get('description', ''))}</li>"
        for skill in payload["skills"]["top_skills"]
    )
    page_items = "".join(
        f"<li><a href='../../{safe(item['path'])}' target='_blank' rel='noopener'>{safe(item['path'])}</a> <span>{safe(item['updated_at'])}</span></li>"
        for item in payload["website"]["recent_pages"]
    )
    report_items = "".join(
        f"<li><a href='../../{safe(item['path'])}' target='_blank' rel='noopener'>{safe(item['path'])}</a> <span>{safe(item['updated_at'])}</span></li>"
        for item in payload["reports"]["dongchedi_summary_md"]
    )
    news_items = "".join(
        f"<li><a href='../../{safe(item['path'])}' target='_blank' rel='noopener'>{safe(item['path'])}</a> <span>{safe(item['updated_at'])}</span></li>"
        for item in payload["reports"]["daily_brief_and_news_md"]
    )
    log_items = "".join(
        f"<li><a href='../../{safe(item['path'])}' target='_blank' rel='noopener'>{safe(item['path'])}</a> <span>{safe(item['updated_at'])}</span></li>"
        for item in payload["task_logs"]
    )
    github_items = "".join(
        f"<li><a href='{safe(item.get('url', '#'))}' target='_blank' rel='noopener'>{safe(item.get('name', 'Unknown'))}</a>"
        f" <span>{safe(item.get('pushed_at', ''))}</span></li>"
        for item in payload["github_projects"]["top_projects"]
    )
    if not github_items:
        github_items = f"<li>{safe(github_empty_text)}</li>"

    decision_items = "".join(
        (
            "<li>"
            f"<strong>{safe(item.get('date', ''))} {safe(item.get('time', ''))}</strong> "
            f"{safe(item.get('title', ''))}<br/>"
            f"<span>{safe(item.get('decision', ''))}</span>"
            "</li>"
        )
        for item in decisions
    )
    if not decision_items:
        decision_items = f"<li>{safe(decision_empty_text)}</li>"

    summary_items = "".join(
        f"<li>{safe(item)}</li>"
        for item in summary_lang.get("overview", [])
        + summary_lang.get("patterns", [])
        + summary_lang.get("lessons", [])
        + summary_lang.get("next_actions", [])
    )

    return f"""<!doctype html>
<html lang=\"{safe('zh-CN' if is_zh else 'en')}\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>{safe(title_page)}</title>
    <style>
        :root {{
            --bg: #f4efe5;
            --panel: #fffdf9;
            --ink: #1c2733;
            --muted: #5a6977;
            --line: #d6c9b3;
            --accent: #0f6a63;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            background: radial-gradient(circle at 15% 0%, #ede2cf 0%, var(--bg) 45%);
            color: var(--ink);
            font-family: Segoe UI, Arial, sans-serif;
            padding: 18px;
        }}
        .wrap {{ max-width: 1200px; margin: 0 auto; display: grid; gap: 14px; }}
        .hero {{
            border-radius: 16px;
            background: linear-gradient(130deg, #0f5a55, #1f3751);
            color: #edf5f6;
            padding: 20px;
        }}
        .hero h1 {{ margin: 0; }}
        .meta {{ margin-top: 6px; color: #d7e7e9; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 14px;
        }}
        .card h2 {{ margin: 0 0 10px; font-size: 18px; color: var(--accent); }}
        ul {{ margin: 0; padding-left: 18px; display: grid; gap: 8px; }}
        li span {{ color: var(--muted); font-size: 12px; margin-left: 6px; }}
        a {{ color: #0e5460; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .full {{ grid-column: 1 / -1; }}
        @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <main class=\"wrap\">
        <section class=\"hero\">
            <h1>{safe(title_page)}</h1>
            <div class=\"meta\">{safe(label_generated_at)}: {safe(payload['generated_at'])} | {safe(label_workspace)}: {safe(payload['workspace_name'])}</div>
            <div class=\"meta\">{safe(label_skills)}: {safe(payload['skills']['count'])} | {safe(label_root_html)}: {safe(payload['website']['root_html'])} | {safe(label_site_html)}: {safe(payload['website']['site_html'])}</div>
        </section>

        <section class=\"grid\">
            <article class=\"card\">
                <h2>{safe(title_skill)}</h2>
                <ul>{skill_items}</ul>
            </article>
            <article class=\"card\">
                <h2>{safe(title_github)}</h2>
                <ul>{github_items}</ul>
            </article>
            <article class=\"card\">
                <h2>{safe(title_decision)}</h2>
                <ul>{decision_items}</ul>
            </article>
            <article class=\"card\">
                <h2>{safe(title_website)}</h2>
                <ul>{page_items}</ul>
            </article>
            <article class=\"card\">
                <h2>{safe(title_dongchedi)}</h2>
                <ul>{report_items}</ul>
            </article>
            <article class=\"card\">
                <h2>{safe(title_news)}</h2>
                <ul>{news_items}</ul>
            </article>
            <article class=\"card\">
                <h2>{safe(title_task)}</h2>
                <ul>{log_items}</ul>
            </article>
            <article class=\"card full\">
                <h2>{safe(title_quick)}</h2>
                <ul>
                    <li><a href=\"latest.md\" target=\"_blank\" rel=\"noopener\">{safe(latest_md_text)}</a></li>
                    <li><a href=\"{safe(payload['generated_at'][:10])}/personal_kb.md\" target=\"_blank\" rel=\"noopener\">{safe(today_md_text)}</a></li>
                    <li><a href=\"notes\" target=\"_blank\" rel=\"noopener\">{safe(notes_text)}</a></li>
                </ul>
            </article>
            <article class=\"card full\">
                <h2>{safe(title_summary)}</h2>
                <ul>{summary_items}</ul>
            </article>
        </section>
    </main>
</body>
</html>
"""


def build_payload(repo_root: Path, top_n_skills: int, recent_limit: int) -> dict[str, Any]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    skill_count, skills = load_skills_catalog(repo_root)
    github_projects = load_github_projects_feed(repo_root, top_n=5)

    website = count_html_pages(repo_root)
    website_recent = collect_recent_files(repo_root, "**/*.html", recent_limit, include_preview=False)

    reports_root = repo_root / "reports"
    dongchedi_summaries = collect_recent_files(
        reports_root,
        "dongchedi_daily/*/summary.md",
        recent_limit,
        include_preview=False,
    )
    brief_and_news = collect_recent_files(
        reports_root,
        "**/*daily*_*.md",
        recent_limit,
        include_preview=False,
    )

    task_logs = collect_recent_files(
        reports_root,
        "task_logs/*.log",
        recent_limit,
        include_preview=True,
    )

    payload = {
        "generated_at": generated_at,
        "workspace_name": repo_root.name,
        "skills": {
            "count": skill_count,
            "top_skills": skills[:top_n_skills],
        },
        "github_projects": github_projects,
        "website": {
            **website,
            "recent_pages": [
                {**asdict(note), "path": to_rel(repo_root, note.path)} for note in website_recent
            ],
        },
        "reports": {
            "dongchedi_summary_md": [
                {**asdict(note), "path": to_rel(repo_root, note.path)}
                for note in dongchedi_summaries
            ],
            "daily_brief_and_news_md": [
                {**asdict(note), "path": to_rel(repo_root, note.path)}
                for note in brief_and_news
            ],
        },
        "task_logs": [
            {**asdict(note), "path": to_rel(repo_root, note.path)} for note in task_logs
        ],
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build personal/project knowledge base snapshot")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Snapshot date")
    parser.add_argument("--top-skills", type=int, default=10, help="How many skills to list")
    parser.add_argument("--recent-limit", type=int, default=12, help="How many recent files to include")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "reports" / "knowledge_base" / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(repo_root, top_n_skills=args.top_skills, recent_limit=args.recent_limit)
    decisions = load_recent_decisions(repo_root, limit=20)
    summary = build_auto_summary(payload, decisions)
    payload["auto_summary"] = summary

    markdown = build_markdown(payload, summary)
    html_text = build_html(payload, decisions, summary, lang="en")
    html_text_zh = build_html(payload, decisions, summary, lang="zh")

    json_path = out_dir / "personal_kb.json"
    latest_json_path = repo_root / "reports" / "knowledge_base" / "latest.json"
    md_path = out_dir / "personal_kb.md"
    latest_path = repo_root / "reports" / "knowledge_base" / "latest.md"
    site_index_path = repo_root / "reports" / "knowledge_base" / "index.html"
    site_index_zh_path = repo_root / "reports" / "knowledge_base" / "index.zh.html"
    latest_html_path = repo_root / "reports" / "knowledge_base" / "latest.html"
    latest_html_zh_path = repo_root / "reports" / "knowledge_base" / "latest.zh.html"
    dated_html_path = out_dir / "personal_kb.html"
    dated_html_zh_path = out_dir / "personal_kb.zh.html"
    token_assets_dir = repo_root / "assets" / "token"
    token_assets_dir.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    latest_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    latest_path.write_text(markdown, encoding="utf-8")
    dated_html_path.write_text(html_text, encoding="utf-8")
    dated_html_zh_path.write_text(html_text_zh, encoding="utf-8")
    site_index_path.write_text(html_text, encoding="utf-8")
    site_index_zh_path.write_text(html_text_zh, encoding="utf-8")
    latest_html_path.write_text(html_text, encoding="utf-8")
    latest_html_zh_path.write_text(html_text_zh, encoding="utf-8")

    # Mirror Token artifacts to a tracked directory so GitHub Pages can serve them.
    (token_assets_dir / "index.html").write_text(html_text, encoding="utf-8")
    (token_assets_dir / "index.zh.html").write_text(html_text_zh, encoding="utf-8")
    (token_assets_dir / "latest.html").write_text(html_text, encoding="utf-8")
    (token_assets_dir / "latest.zh.html").write_text(html_text_zh, encoding="utf-8")
    (token_assets_dir / "latest.md").write_text(markdown, encoding="utf-8")
    (token_assets_dir / "latest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Knowledge base written: {md_path}")
    print(f"JSON snapshot written: {json_path}")
    print(f"Latest JSON snapshot written: {latest_json_path}")
    print(f"Latest snapshot written: {latest_path}")
    print(f"Knowledge base site written: {site_index_path}")
    print(f"Knowledge base site (zh) written: {site_index_zh_path}")
    print(f"Token assets written: {token_assets_dir}")


if __name__ == "__main__":
    main()
