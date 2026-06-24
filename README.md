# C7 OTA Hub

面向法规评审与技术对齐的静态门户仓库，当前最小发布面包含：

- `index.html`: 门户首页入口
- `c7_regulation_tabs.html`: C7 OTA Regulation Hub 主页面
- `.github/workflows/pages.yml`: GitHub Pages 发布流程

## Live Site

- Portal home: `https://ttoriaa.github.io/C7-OTA-Hub/`
- Regulation hub: `https://ttoriaa.github.io/C7-OTA-Hub/c7_regulation_tabs.html`

## Scope

- 统一展示 C7 OTA 法规五个模块
- 支持中英切换、章节导航、条款筛选、章节内命中高亮
- 适合做法规解读、评审演示、条款映射与门户化浏览

## Local Preview

直接打开 `index.html` 或 `c7_regulation_tabs.html` 即可预览。

如果需要本地 HTTP 预览，可在仓库根目录执行：

```powershell
python -m http.server 8000
```

然后访问 `http://localhost:8000/`。

## Deployment

推送到 `main` 后，GitHub Actions 会自动发布 GitHub Pages。
当前 workflow 只打包最小静态产物：

- `index.html`
- `c7_regulation_tabs.html`
- `assets/`（如果存在）

这样可以避免把当前仓库里无关的历史文件一起发布出去。
