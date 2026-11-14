# Three ways to start with Paper Radar

[Interactive starting point](https://eliot5566.github.io/JEV-Paper-Radar/try/)
· [繁體中文](https://eliot5566.github.io/JEV-Paper-Radar/try/?lang=zh)
· [Install the Claude skill](claude-install.md)

## 1. Check the output before sharing your own material

Start with the [saved real-paper test](https://eliot5566.github.io/JEV-Paper-Radar/try/real/)
and [two-link trial guide](first-run.md). Its summaries are labelled and the
metadata API failure/web-tool recovery is disclosed. The separate fictional
demo below remains useful for an offline installation check.

Open the public fictional demo or upload the skill and ask:

> Use paper-radar to run its bundled offline demo. Do not install packages, use
> network access or ask for an API key. Give me HTML and RSS, and confirm the
> number of fictional records.

Expected workflow: 44 fictional new-paper records, HTML and RSS. The scores use
keyword rules, so this checks installation and layout, not Claude accuracy.

## 2. Start with a research interest or links (skill 0.2.0)

You do not need to prepare abstracts or CSV. Ask:

> Use paper-radar to find up to 10 papers from the last 30 days about benchmarks
> for tool-using LLM agents. Retrieve the titles and abstracts, rank in this
> conversation and export HTML, CSV, JSON and RSS. Show sources and failures.

Or provide arXiv, PubMed or DOI links plus a reading interest. The skill resolves
their public metadata itself. Search uses arXiv or PubMed; DOI metadata comes
from Crossref and may have no abstract. Missing records stay in the retrieval
audit and are not scored. Queries and IDs go to public sources; do not put
private research details into a public query. Retrieval needs permitted network
access or existing Claude web tools. Web summaries are labelled as such.

In a Claude web link test, the metadata API was blocked by that environment.
Existing web tools read the two official arXiv pages, and the exporter retained
the resulting web-summary provenance. This demonstrates that fallback in the
tested account, not access guarantees for every account or source.

### Or bring an existing reading pile

Start with 5–20 abstracts from your own reading queue. The
[blank CSV template](../showcase/samples/papers-template.csv) has columns
`id,title,abstract,url`. Preserve source IDs where available; leave an unknown
URL blank. A [three-paper fictional CSV](../showcase/samples/fictional-abstracts.csv)
is available to test the process before sharing actual research.

Upload the CSV to Claude after installing the skill and ask:

> Use paper-radar to rank the attached titles and abstracts for this interest:
> benchmarks evaluating tool-using LLM agents. Score them in this conversation,
> preserve all IDs and low-scoring papers with reasons, and export HTML, CSV,
> JSON and RSS with the bundled exporter. Make no extra API calls. Label sample
> material as fictional when applicable. Scores are uncalibrated; chat usage and
> cost are unknown. Ask for the abstracts if none were attached.

Replace the interest with one concrete statement. For example:

| Field | One interest to try |
|---|---|
| LLM evaluation | Benchmarks for evaluating tool-using LLM agents |
| Efficient inference | Methods for reducing language-model inference memory usage |
| Neuroscience | Neural mechanisms of memory consolidation during sleep |

Inspect reasons and near misses. A low score is a triage signal, not a reason
to discard a study permanently. The skill uses only supplied titles and abstracts;
it does not establish the truth or quality of a paper from full-text review.

## 3. Make it a continuing research habit

If an existing topic fits, subscribe to a
[public Jev feed](https://eliot5566.github.io/JEV-Paper-Radar/public/) without
installing anything. Those feeds are not outputs from the uploaded Claude skill.

For a personal daily radar, use the [Claude API example](https://github.com/Eliot5566/paper-radar-claude-example)
and [API guide](claude-quickstart.md). Scheduling, network access, API credentials
and billing are separate setup steps. An uploaded skill does not create a daily
background job or keep exported files indefinitely.

For threshold checks, label both selected and unselected papers personally.
Fit on one batch, then check on a later, separately labelled batch. Model-made
scores are not independent human labels, and fitting scores are not held-out
performance.

## 繁體中文：第一次使用的順序

1. 到[公開試用頁](https://eliot5566.github.io/JEV-Paper-Radar/try/?lang=zh)先看成品。
2. 上傳啟用 0.2.0 技能，可先跑虛構示範確認安裝。
3. 直接描述興趣與日期範圍，或貼 arXiv／PubMed／DOI 連結；技能取得標題摘要再排序，不必先做 CSV。已有摘要也可直接貼上或附檔。
4. 要求保留全部 ID 與未入選項目，匯出網頁、CSV、JSON、RSS；檢查理由和漏掉的相關論文。
5. 確認對你的領域有幫助後，再考慮每日 API 自動化，不必在第一次試用時就設定金鑰或排程。

對話模式仍使用 Claude 方案額度。請只提供有權分享的資料，不要貼 API 金鑰或未授權的私人研究。

## Useful first-run feedback

Use the [setup form](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=setup-help.yml)
for a problem, or [Discussions](https://github.com/Eliot5566/JEV-Paper-Radar/discussions/21)
for an experience report. Include the research field, local/Claude/Actions
environment, version, first step attempted, expected result and what happened.
Redact errors and configuration before sharing. A factual experience report
helps determine the next improvement; it is not a requirement to endorse the tool.
