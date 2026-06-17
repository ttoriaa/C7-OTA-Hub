# Skills Index

This index helps team members quickly discover and invoke available skills.

## Dongchedi Skills

### 1. dongchedi-charging-confluence-pipeline

Use when:
- You want one workflow to run Dongchedi charging daily processing and publish/update Confluence.

Path:
- [dongchedi-charging-confluence-pipeline/SKILL.md](dongchedi-charging-confluence-pipeline/SKILL.md)

Quick invoke:
- `/dongchedi-charging-confluence-pipeline`
- `/dongchedi-charging-confluence-pipeline date=2026-06-17 publish=false`

### 2. dongchedi-charging-performance-summary

Use when:
- You need extraction and structured comparison of charging fields from Dongchedi parameter pages.

Path:
- [dongchedi-charging-performance-summary/SKILL.md](dongchedi-charging-performance-summary/SKILL.md)

Quick invoke:
- `/dongchedi-charging-performance-summary 对这 5 个懂车帝 URL 生成充电性能对比总结`

## Add New Skills

When adding a new skill:
1. Create a folder under `.github/skills/<skill-name>/`.
2. Add `SKILL.md` with complete frontmatter and usage guidance.
3. Append a new section in this index with purpose, path, and quick invoke examples.
