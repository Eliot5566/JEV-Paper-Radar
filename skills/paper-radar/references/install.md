# Install and first use / 安裝與第一次使用

## Claude chat (web or desktop)

Enable code execution/file creation, then open Customize → Skills → + → Create
skill → Upload a skill. Select the complete paper-radar-claude.zip archive,
enable Paper Radar, and start a new chat. Organization settings can restrict
skill creation or code execution; ask the account owner if the controls are absent.

Try: "Use the paper-radar skill to run its bundled offline demo. Do not install
packages, use network access or request an API key. Give me the HTML and RSS."

Next: "Use paper-radar to rank the fictional abstracts in examples/papers.json
for benchmarks evaluating tool-using LLM agents. Export HTML, CSV, JSON and RSS,
and explain that the current chat made the scores."

For your own work, provide an interest and titles/abstracts you are authorized
to share with Claude. The conversation-native mode uses normal Claude plan
usage; it needs no separate API key or external data service. It is not an
automatic background research feed. Keep your exported files yourself.

## Claude Code

Extract the archive. Place its paper-radar folder in .claude/skills/ for a project,
or ~/.claude/skills/ for personal use, after checking for an existing custom skill.
Invoke /paper-radar. The full ZIP bundles the CLI, so no pip install is needed.
A source-folder copy can use a separately installed CLI; see live-api.md.

## 繁體中文

先開啟 Claude 的程式執行／檔案建立功能，再到「自訂 → 技能」上傳完整 ZIP，
啟用 Paper Radar，開始新的對話。組織管理員可能限制這些功能。

第一次可說：「使用 paper-radar 技能跑內附離線示範，不安裝套件、不連網、
不要求 API 金鑰，提供 HTML 與 RSS。」示範使用 44 篇虛構論文與關鍵字規則。

接著提供自己的研究興趣、論文標題與摘要，Claude 可在目前對話中評分，
輸出網頁、CSV、JSON、RSS。不需額外 API 金鑰，但仍使用 Claude 對話方案額度。
分數是助理自述、不是校準後的機率；程式無法取得對話 token 或費用，記為未知。

自動抓取新論文、排程與額外 API 判斷使用本機 CLI 或 GitHub Actions，
另需網路、私下設定的金鑰與 API 費用。安裝技能本身不會開啟排程或公開資料。

## Package contents

- SKILL.md: workflow instructions (description under 200 characters)
- scripts/run.py: bundled CLI entry point
- scripts/chat_report.py: offline, validated chat-score exporter
- vendor/paper_radar/: Python source and fictional demo data
- examples/papers.json: three fictional abstracts without prewritten scores
- references/: format, setup, live-API notes and starter configuration
- LICENSE and bundle-manifest.json: attribution and file hashes

No API keys, environment files, real user abstracts or private data are bundled.
