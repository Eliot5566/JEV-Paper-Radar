# Install Paper Radar in Claude

[繁體中文](#繁體中文) · [API automation guide](claude-quickstart.md)

**[Preview examples before installing](https://eliot5566.github.io/JEV-Paper-Radar/try/)**
· [繁體中文試用入口](https://eliot5566.github.io/JEV-Paper-Radar/try/?lang=zh)
· [Try two real links](first-run.md)
· [Three practical starting workflows](recipes.md)

The 0.2.0 upload bundle includes public-paper retrieval, the CLI, fictional sample
data and a conversation report exporter. Python 3.11+ and Claude's code execution/
file creation feature are required. No pip install or separate model API key is
needed. Public retrieval needs permitted network access or existing Claude web
tools; the offline demo and pasted-abstract mode do not. Normal Claude
conversation usage still applies. CSV preparation is optional.

## Download and enable

Download **paper-radar-claude-v0.2.0.zip** from the
[Claude skill release](https://github.com/Eliot5566/JEV-Paper-Radar/releases/tag/claude-skill-v0.2.0).
Upload that ZIP as-is; the full repository source ZIP has a different structure.

In Claude, open **Customize → Skills → + → Upload Skill** (some layouts show
Create skill → Upload a skill). Select the ZIP, complete the upload scan and
enable `paper-radar`. Start a new conversation or choose **Try in chat**.
An organization administrator may restrict uploads or code execution.

Already installed 0.1.0? Open the existing paper-radar skill → more options →
Replace, upload the new ZIP, keep it enabled and start a new chat. It does not
update automatically when the repository changes.

### Start with just an interest or paper links

> Use paper-radar to find up to 10 arXiv papers from the last 30 days about
> benchmarks evaluating tool-using LLM agents. Retrieve their titles and
> abstracts, rank them in this conversation, and give me HTML, CSV, JSON and RSS.
> Show the query, sources and any failures. Do not call a separate model API.

Or:

> Use paper-radar for https://arxiv.org/abs/2308.03688 and
> https://arxiv.org/abs/2302.04761. My interest is evaluating LLM agents and tool
> use. Retrieve the abstracts yourself, rank them and export HTML and RSS.

The skill creates the input files itself. Supported direct identifiers are
arXiv abs/pdf/html links or IDs, PubMed links/PMIDs, and DOI/doi.org identifiers.
Search uses arXiv or PubMed, with 10 candidates and a 30-day window by default;
explicit user limits/dates take precedence. It is not exhaustive retrieval.
PubMed's window uses indexing date. DOI resolution uses Crossref; many DOI
records lack abstracts. Missing/failed records are disclosed, not scored.

Search terms and public paper identifiers are sent to the chosen public source.
These metadata requests do not use a model API key. Do not include private
research details in public search queries. The retriever does not scrape
arbitrary publisher pages, download full PDFs or bypass paywalls.

If code execution cannot reach the source, the skill may use existing permitted
Claude web tools, record that fallback and distinguish summaries from original
abstracts. If neither route works, it explains the limitation; installing the
skill does not grant network permissions. See [retrieval details](../skills/paper-radar/references/retrieval.md).

### First use

> Use the paper-radar skill to run its bundled offline demo. Do not install
> packages, use network access or request an API key. Give me the HTML and RSS.

The 44 sample papers are fictional and scores come from a keyword heuristic.
This checks installation and output, not Claude accuracy.

### Rank supplied abstracts

> Use paper-radar to rank the paper titles and abstracts below for my interest:
> benchmarks evaluating tool-using LLM agents. Use this conversation to score
> all papers and export HTML, CSV, JSON and RSS. Explain why each paper matched.

Then paste the abstracts or attach a file; CSV is not required. With an interest
or supported links but no abstracts, the skill retrieves first. Its exporter validates scores and IDs,
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

The offline demo is tested without site packages and with HTTP connections
blocked; retrieval tests use controlled responses and real public-source smoke
checks separately. CI checks the complete suite and builds the archive on Python 3.11,
3.12 and 3.13. SHA-256 hashes of bundled files and the source commit are stored
in `bundle-manifest.json`; no keys or real-user research data are packaged.

Claude web conversation testing with Opus 5.5 loaded the uploaded skill, ran
Paper Radar 0.2.0 on 44 fictional demo papers and exported a separate three-paper
conversation report using the bundled exporter. This establishes those two
workflows in that account and environment. In the 0.2.0 web test, two supplied
arXiv links and a separate interest-only query (three recent papers) completed
ranking and export without a user-prepared CSV. The metadata API was blocked;
existing Claude web tools read official pages and returned summaries explicitly
labelled web-summary. The search test disclosed additional unread candidate hits.
Local public API smoke checks separately retrieved arXiv and PubMed abstracts;
two tested Crossref DOIs had no abstracts and were retained as unscored omissions.
Functional checks do not establish accuracy
on research, exhaustive coverage or mobile/desktop-client compatibility.

## Build the upload ZIP from source

```sh
python scripts/build_claude_skill.py --output dist/paper-radar-claude.zip --source-commit YOUR_COMMIT_SHA
```

The build uses the standard library and normalizes text line endings. It includes
only the skill's Markdown/Python/JSON files, the Python runtime and fictional demo
fixtures, the starter configuration and MIT license. Generated data, environment
files and bytecode are excluded. CI also retains the ZIP as a workflow artifact.

## 繁體中文

1. 從[技能版本頁](https://github.com/Eliot5566/JEV-Paper-Radar/releases/tag/claude-skill-v0.2.0)
   下載 `paper-radar-claude-v0.2.0.zip`，不要使用整份專案的 Source code ZIP。
2. Claude「自訂 → Skills → 新增 → 上傳 Skill」，上傳完整 ZIP，啟用 `paper-radar`。
   若找不到功能，確認已開啟程式執行／檔案建立，或詢問組織管理員。
3. 新開對話，輸入：「用 paper-radar 跑內附離線示範，不安裝套件、不連網、
   不要求 API 金鑰，提供 HTML 與 RSS。」
4. 直接提供研究興趣，或 arXiv／PubMed／DOI 連結，請技能取得標題摘要，
   再在目前對話排序，輸出網頁、CSV、JSON、RSS；不必先整理 CSV。
   公開檢索需要環境允許連線或既有網頁工具，不需額外模型 API 金鑰，
   仍使用 Claude 對話額度。缺摘要、失敗及不支援的連結會列出。
5. 已安裝舊版者，到技能的更多選項選「取代」，上傳新版後新開對話。

目前已在 Claude 網頁版 Opus 5.5 對話中驗證載入技能、44 篇離線示範與三篇虛構摘要的
對話內排序／匯出；0.2.0 另完成兩篇真實連結、只給興趣找三篇近期論文的流程。
測試帳號擋住 metadata API，實際透過既有網頁工具取得摘要重述並標為 web-summary，
也揭露搜尋候選先選取的範圍；沒有宣稱取得逐字原始摘要或完整文獻。
這些是功能驗收，不是準確率評估，也不代表所有客戶端相容。

分數是自述的相關性判斷，不是校準過的機率。對話用量與費用無法由此程式取得，
因此報告保留未知，不宣稱免費。RSS 須部署到固定網址才能訂閱。

「安裝即可開始用」只指離線示範與提供摘要後的對話內排序；自動抓取、背景排程、
額外 API 判斷與公開發布仍需另外設定，詳見[原本入門教學](claude-quickstart.zh-TW.md)。
