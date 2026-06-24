---
name: token-tab-github-daily-sync
description: "每天基于 GitHub 项目变更刷新 Token tab 内容：同步 github projects feed，并重建 knowledge base summary。Use when you need a daily Token tab refresh driven by GitHub updates."
argument-hint: "可选参数: username=ttoriaa, limit=12, top_skills=12, recent_limit=15, include_homepage_any_domain=true|false, include_project_boards=true|false, project_board_limit=20"
user-invocable: true
disable-model-invocation: false
---

# Token Tab GitHub Daily Sync

## Purpose
将 Token tab 的内容更新流程固化为每日可重复执行的单一动作：
1. 从 GitHub 拉取最新公开项目到 `assets/github-projects.json`。
2. 基于最新 feed 重建知识库产物（含 `latest.json` 自动总结）。
3. 让 `index.html` 的 Token tab 首屏 summary 与 iframe 内容同时反映最新记录。

## When To Use
- 你希望 Token tab 每天自动反映 GitHub 项目新增/更新。
- 你希望减少手工执行多个脚本，改为一个 daily runner。
- 你需要可用于 VS Code Task / Windows Scheduler / GitHub Actions 的统一命令。

## Inputs
- `username` (default `ttoriaa`): GitHub 用户名。
- `limit` (default `12`): 最多拉取多少 GitHub 项目进入 feed。
- `top_skills` (default `12`): knowledge base 里保留多少技能条目。
- `recent_limit` (default `15`): knowledge base 最近文件窗口。
- `include_homepage_any_domain` (default `false`): 是否包含任意 homepage 域名项目。
- `include_project_boards` (default `false`): 是否包含 GitHub project boards。
- `project_board_limit` (default `20`): board 抓取上限。

## Implementation Surface
- Runner: `scripts/run_token_github_daily_sync.py`
- GitHub feed sync: `scripts/sync_github_projects.py`
- Token summary rebuild: `scripts/build_personal_knowledge_base.py`
- Token UI data source: `reports/knowledge_base/latest.json`

## Command
```bash
.\.venv\Scripts\python.exe .\scripts\run_token_github_daily_sync.py --username ttoriaa --limit 12 --top-skills 12 --recent-limit 15
```

## Optional Flags
```bash
.\.venv\Scripts\python.exe .\scripts\run_token_github_daily_sync.py \
  --username ttoriaa \
  --limit 15 \
  --include-homepage-any-domain \
  --include-project-boards \
  --project-board-limit 20
```

## Output Contract
执行成功后至少更新：
- `assets/github-projects.json`
- `reports/knowledge_base/latest.json`
- `reports/knowledge_base/latest.md`
- `reports/knowledge_base/latest.html`
- `reports/knowledge_base/index.html`

## Validation
- 打开主站 Token tab，确认首屏出现最新 `Auto Summary and Lessons` 内容。
- 点击 Token tab 内 `Open Token Site`，确认 iframe 页面包含最新 GitHub 项目更新卡片。

## Failure Handling
- GitHub 请求失败：检查网络或 `GITHUB_TOKEN`（若启用 boards）。
- 数据未变化：属于正常情况，summary 仍会按当前记录重建。
- Token tab 未更新：刷新浏览器缓存（`Ctrl+F5`）后重试。
