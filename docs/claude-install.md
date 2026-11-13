# Install Paper Radar in Claude

[繁體中文](#繁體中文) · [API automation guide](claude-quickstart.md)

The upload bundle includes the CLI, fictional sample data and a conversation
report exporter. Python 3.11+ and Claude's code execution/file creation feature
are required. The first two modes need no pip install, separate API key or
network access. Normal Claude conversation usage still applies.

## Download and enable

Download **paper-radar-claude.zip** from the
[Claude skill release](https://github.com/Eliot5566/JEV-Paper-Radar/releases/tag/claude-skill-v0.1.0).
Upload that ZIP as-is; the full repository source ZIP has a different structure.

In Claude, open **Customize → Skills → + → Upload Skill** (some layouts show
Create skill → Upload a skill). Select the ZIP, complete the upload scan and
enable `paper-radar`. Start a new conversation or choose **Try in chat**.
An organization administrator may restrict uploads or code execution.

### First use

> Use the paper-radar skill to run its bundled offline demo. Do not install
> packages, use network access or request an API key. Give me the HTML and RSS.

The 44 sample papers are fictional and scores come from a keyword heuristic.
This checks installation and output, not Claude accuracy.

### Rank supplied abstracts

> Use paper-radar to rank the paper titles and abstracts below for my interest:
> benchmarks evaluating tool-using LLM agents. Use this conversation to score
> all papers and export HTML, CSV, JSON and RSS. Explain why each paper matched.

Then provide the abstracts. With no input, the skill asks for papers or offers
three explicitly fictional examples. Its exporter validates scores and IDs,
sorts records and preserves low-scoring papers in HTML/CSV/JSON. RSS contains
the shortlisted papers; it needs hosting before it can be subscribed to.

Scores are self-reported relevance judgements, not calibrated probabilities or
independent labels. The report records conversation token usage and cost as
unknown, not zero. The exporter makes no separate API requests. Do not upload
credentials; use only research material you are authorized to share with Claude.

## Automation is a separate mode

This upload does not create a daily background task, persist files indefinitely
or publish a site. Fetching new feeds and scheduling API judging uses the
[local/GitHub workflow](claude-quickstart.md), with network access and privately
configured credentials. External API judging is separately billed.

For Claude Code, extract the ZIP and copy its `paper-radar` folder into a project's
`.claude/skills/`, or your personal `~/.claude/skills/`, after reviewing any existing
destination. Invoke `/paper-radar`. The complete ZIP includes the runtime; a
copy of the source skill directory alone uses a separately installed CLI.

## Verification scope

The bundle is tested locally without site packages and with HTTP connections
blocked. CI checks the complete suite and builds the archive on Python 3.11,
3.12 and 3.13. SHA-256 hashes of bundled files and the source commit are stored
in `bundle-manifest.json`; no keys or real-user research data are packaged.

Claude web conversation testing with Opus 5.5 loaded the uploaded skill, ran
Paper Radar 0.2.0 on 44 fictional demo papers and exported a separate three-paper
conversation report using the bundled exporter. This establishes those two
workflows in that account and environment. It does not establish performance
on real research, mobile/desktop-client compatibility or live API connectivity.

## Build the upload ZIP from source

```sh
python scripts/build_claude_skill.py --output dist/paper-radar-claude.zip --source-commit YOUR_COMMIT_SHA
```

The build uses the standard library and normalizes text line endings. It includes
only the skill's Markdown/Python/JSON files, the Python runtime and fictional demo
fixtures, the starter configuration and MIT license. Generated data, environment
files and bytecode are excluded. CI also retains the ZIP as a workflow artifact.

## 繁體中文

1. 從[技能版本頁](https://github.com/Eliot5566/JEV-Paper-Radar/releases/tag/claude-skill-v0.1.0)
   下載 `paper-radar-claude.zip`，不要使用整份專案的 Source code ZIP。
2. Claude「自訂 → Skills → 新增 → 上傳 Skill」，上傳完整 ZIP，啟用 `paper-radar`。
   若找不到功能，確認已開啟程式執行／檔案建立，或詢問組織管理員。
3. 新開對話，輸入：「用 paper-radar 跑內附離線示範，不安裝套件、不連網、
   不要求 API 金鑰，提供 HTML 與 RSS。」
4. 接著提供研究興趣、論文標題及摘要，請它在目前對話中評分並輸出網頁、CSV、
   JSON、RSS。不需額外 API 金鑰，但仍使用 Claude 方案的對話額度。

目前已在 Claude 網頁版 Opus 5.5 對話中驗證載入技能、44 篇離線示範與三篇虛構摘要的
對話內排序／匯出。這不是準確率評估，也未據此宣稱手機、桌面客戶端或真實 API 已驗證。

分數是自述的相關性判斷，不是校準過的機率。對話用量與費用無法由此程式取得，
因此報告保留未知，不宣稱免費。RSS 須部署到固定網址才能訂閱。

「安裝即可開始用」只指離線示範與提供摘要後的對話內排序；自動抓取、背景排程、
額外 API 判斷與公開發布仍需另外設定，詳見[原本入門教學](claude-quickstart.zh-TW.md)。
