# Claude 使用者的 Paper Radar 入門

[English](claude-quickstart.md) · [專案介紹](../README.zh-TW.md) · [使用量與費用](usage-and-cost.md)

用一句白話描述研究興趣，把新論文整理成每日網頁與 RSS。
Paper Radar 將標題、摘要送給判斷模型，再由 Python 排序；它只讀摘要，
不能取代完整文獻審查。程式採 MIT 授權，需要 Python 3.11 以上，沒有執行期相依套件。

## 選擇你的起點

| 想做的事 | 從這裡開始 | 需要什麼 |
|---|---|---|
| 看看輸出長什麼樣 | 下方離線示範 | Python；不需金鑰 |
| 直接閱讀現成內容 | [公開雷達](https://eliot5566.github.io/JEV-Paper-Radar/public/) | 瀏覽器或 RSS 閱讀器；這些內容使用 Jev |
| 用 Claude 跑自己的興趣 | 下方小量試跑 | Anthropic API 帳號與另外計費的使用量 |
| 每天自動發布 | [Claude 範例專案](https://github.com/Eliot5566/paper-radar-claude-example) | GitHub、API secret、Pages |
| 請 Claude Code 協助設定 | 下方選用技能 | Claude Code；真實判斷仍需 API 金鑰 |

Claude 聊天訂閱與 API 分開計費。此程式讀取 `ANTHROPIC_API_KEY`，
不會將 Claude Code 登入當作 API 金鑰使用。詳見 [Anthropic 說明](https://support.claude.com/en/articles/8325606-what-is-the-pro-plan)。

## 1. 不需金鑰的離線示範

```sh
python -m pip install "paper-radar==0.2.0"
paper-radar --version
paper-radar demo --out paper-radar-demo
```

在瀏覽器開啟 `paper-radar-demo/site/index.html`。示範使用虛構論文與關鍵字規則，
可檢查安裝與頁面功能，不能用來證明 Claude 準確率或 API 連線正常。

## 2. 先驗證設定

下載 [`profiles/claude-starter.toml`](../profiles/claude-starter.toml)，在新的工作資料夾
存成 `radar.toml`，把興趣改成你關心的一個明確主題，再執行：

```sh
paper-radar check -c radar.toml --show-questions
```

這一步不需金鑰或網路。入門設定限制每次最多 20 篇、同時 2 個請求；
分數門檻只是畫面分類起點，沒有已驗證的精確率或召回率保證。
設定內的輸入／輸出單價附有日期，正式執行前請確認模型與適用長度級距。
20 篇上限不是金額預算；重試、重跑仍可能增加費用，事前估算也只包含輸入。

## 3. 小量執行真實資料

在自己的 shell 私下設定 `ANTHROPIC_API_KEY`，或放在 `radar.toml` 旁的 `.env`。
若使用 Git，先將 `.env` 加入 `.gitignore`。不要把金鑰貼到聊天、issue 或設定檔。

```sh
paper-radar run -c radar.toml --limit 20 --dry-run
paper-radar run -c radar.toml --limit 20 --no-notify
```

第一行會連網抓清單、估算輸入，不呼叫判斷模型；但建立 Claude backend 仍要求
金鑰已設定。第二行會產生 API 費用。完成後開啟 `site/index.html`；發布到固定網址後，
可訂閱 `site/feed.xml`。輸出相對路徑以設定檔所在資料夾為基準；沒有公告新論文的日子
可能沒有新結果。

檢查 `data/usage.jsonl` 與 `data/runs.jsonl`。0.2.0 會保留供應商回報的輸入、
輸出與快取用量，包含格式修復和失敗請求；缺少用量或單價會顯示**費用未知**。
這不是供應商帳單，額外 TL;DR 生成也不在稽核範圍，詳見[費用說明](usage-and-cost.md)。

## 4. 用自己的判斷檢查結果

Claude 輸出的是自述分數，不能直接當作校準過的機率。檢查入選與未入選的論文，
標註自己的判斷，再調整門檻：

```sh
paper-radar label arxiv:2609.01234 yes -c radar.toml
paper-radar label arxiv:2609.04321 no -c radar.toml
paper-radar calibrate -c radar.toml --precision 0.9 --recall 0.9
```

將範例 ID 換成這次執行已儲存的論文。也要標註未入選內容，才有機會發現漏掉的
相關論文。同一批資料用來選門檻又評分，不是獨立驗證；請再用之後另一批、分開標註
的資料檢查。資料不足以支持目標時，應增加標註，不要宣稱目標已達成。

[49 篇初步觀察](claude-calibration.md)的標註來自助理，並非維護者本人；
其門檻不代表新領域的準確率。主 README 的 Cochrane 成績使用 Jev，不能套到 Claude。

## 選用：讓 Claude Code 協助

先檢閱 [`skills/paper-radar/SKILL.md`](../skills/paper-radar/SKILL.md)，
複製此專案後，將整個技能資料夾放到使用專案的 `.claude/skills/paper-radar/`。
個人共用安裝位置是 `~/.claude/skills/paper-radar/`；詳見[官方技能文件](https://code.claude.com/docs/en/skills)。

在專案根目錄，macOS／Linux 可使用：

```sh
mkdir -p .claude/skills
cp -R skills/paper-radar .claude/skills/paper-radar
```

PowerShell：

```powershell
New-Item -ItemType Directory -Force .claude/skills
Copy-Item -Recurse skills/paper-radar .claude/skills/paper-radar
```

若目標資料夾已存在，先檢查內容，避免覆蓋自訂技能。在該專案開啟 Claude Code，輸入：

> /paper-radar 幫我設定 agent 評測論文雷達。先驗證設定、跑離線示範，
> 正式 API 執行前列出篇數上限與預估用量。金鑰不要出現在聊天或追蹤檔案中。

安裝技能不會自動加入金鑰、開啟 GitHub 排程或發布網頁。

## 自動發布與回饋

[Claude 範例專案](https://github.com/Eliot5566/paper-radar-claude-example)包含固定到
`v0.2.0` 的完整 Pages 流程。Fork 後啟用 workflows、設定 secret 與 Pages，
第一次手動執行在 limit 填 `20`。範例排程為工作日 UTC 06:00（台灣 14:00）；
GitHub 排程可能延遲，資料來源也有各自更新時間。

[回報設定問題](https://github.com/Eliot5566/JEV-Paper-Radar/issues/new?template=setup-help.yml)
或在[討論區分享使用經驗](https://github.com/Eliot5566/JEV-Paper-Radar/discussions)。
可提供領域、版本、backend／model、首次執行結果與遮蔽敏感資訊後的錯誤。
僅分享可公開的少量設定，不要附上 API 金鑰、整份環境變數、私人摘要或未公開研究。
