# Try Paper Radar with real papers

[繁體中文](#繁體中文) · [Install or update the skill](claude-install.md) · [Saved real-paper result](https://eliot5566.github.io/JEV-Paper-Radar/try/real/)

You do not need a CSV, a separate model API key or a Python installation on your
own computer for the Claude upload workflow. You do need the enabled skill,
Claude code execution/file creation, and permitted network access or existing
Claude web tools for public retrieval. Normal Claude plan usage applies.

## 1. Start with two known links

Install [skill 0.2.0](https://github.com/Eliot5566/JEV-Paper-Radar/releases/tag/claude-skill-v0.2.0).
For an existing installation, use paper-radar → more options → Replace, upload
the new ZIP, keep it enabled and start a new conversation. Do not use the
repository's Source code ZIP.

Paste this prompt; no file attachment is needed:

> Use paper-radar for https://arxiv.org/abs/2308.03688 and
> https://arxiv.org/abs/2302.04761. My interest is evaluating LLM agents and tool
> use. Retrieve their titles and abstracts yourself, rank them in this
> conversation, and export HTML, CSV, JSON and RSS. Preserve source IDs and
> retrieval provenance, disclose missing abstracts and failures, and label any
> web summaries. Do not call a separate model API or change network permissions.

These are real papers: AgentBench and Toolformer. The saved result is one
functionality test, not a target score to reproduce. Its scores were 0.93 and
0.74; another conversation can reasonably differ. The tested account blocked
the metadata API, so existing Claude web tools read the official pages and
returned explicitly labelled summaries. No full-text review was performed.

Check the useful parts rather than matching those numbers:

- Both source IDs appear once, with the right title and URL.
- Reasons relate to your stated interest and the available abstract/summary.
- HTML opens; CSV/JSON retain both papers and their provenance. RSS contains
  must-read and maybe papers; it can legitimately be empty for another request.
- Missing or failed records are disclosed; a blocked route is not called a
  successful API fetch. A labelled web summary is not an original abstract.

## 2. Then try your own interest

> Use paper-radar to find up to 5 papers from the last 30 days on methods for
> evaluating multi-step tool-using LLM agents. Retrieve public titles and
> abstracts, show the query/source/date range and rank in this conversation.
> Export HTML and RSS, preserving all scored IDs and disclosing failures or
> unread search candidates. Do not silently widen an empty search or call a
> separate model API.

Replace the interest with your broad public topic. Search sends the query or
identifiers to public sources or existing web tools, so leave private plans out.
The candidate limit is not a claim to read every paper in a field. PubMed's
date window uses indexing date; arXiv uses submission date. Crossref DOI records
often lack an abstract, and arbitrary publisher pages/PDFs are not automatically
scraped. If neither retrieval route is available, use pasted abstracts or the
fictional offline demo; do not change security/network settings just to finish.

## 3. Tell us what happened

[Share a first-run experience](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=first-run.yml)
whether it worked or failed. Include the version, environment, route and one
concrete observation. Posting is optional and public. Keep private paper text,
credentials, personal details and full chat logs out.

For ranking feedback, inspect selected and unselected papers. A public ID plus
your own relevance judgement and reason is useful. A few examples do not establish
precision/recall; model-made scores are not independent human labels.

If you only need troubleshooting, use [setup help](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=setup-help.yml).
An exported RSS file needs a stable public URL before it becomes a subscription;
the skill does not start daily schedules, host files or preserve them forever.

## 繁體中文

1. 安裝或以「取代」更新到技能 0.2.0，保持啟用並新開對話。
2. 貼上這段，不需要 CSV 或附檔：

> 用 paper-radar 讀 https://arxiv.org/abs/2308.03688 和
> https://arxiv.org/abs/2302.04761。我關心 LLM agent 評測與工具使用。
> 請自行取得標題摘要，在目前對話排序，輸出 HTML、CSV、JSON、RSS。
> 保留 ID、來源、缺摘要與失敗紀錄；網頁摘要重述要標示。不使用額外模型 API，
> 不更改網路權限。

3. 核對兩篇標題、ID、理由與檔案，再試自己的興趣：「找最近 30 天最多 5 篇……」。
4. 成功或卡住都可填[首次使用回饋](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=first-run.yml)。
   只分享版本、環境、方式與可公開的具體經驗，不貼私人摘要、金鑰或完整對話。

公開快照是已完成的功能測試，不是即時搜尋、準確率或其他使用者採用的證據。
對話分數未校準；一般 Claude 方案額度仍會使用，token 與費用未知。
