# Paper Radar 論文雷達：專案企劃

> 一句話定位：**讓 Jev 每天讀完 arXiv／bioRxiv 上所有新論文，只把真正該讀的幾篇交給你。Fork 即用、零伺服器，讀完整個 arXiv 一天約 6 美分。**

本文件整理了三件事：為什麼選這個方向、產品怎麼設計、怎麼讓它在 GitHub 上長出大量 star。附帶的 MVP 程式碼已可執行，並通過 66 個測試。

---

## 1. 為什麼是這個方向

### 1.1 Jev 真正的優勢是「規模」，不是「聰明」

依官方資料，Jev 的特性是：

- 輸入 $0.042／百萬 token，**輸出免費**；端到端延遲 70–500ms（[官方發表文](https://typesafe.ai/blog/introducing-system-one-models-and-jev)）
- 只回傳型別化的答案（Choice／Score／Noul）與機率，不生成文字，所以不會輸出選項以外的東西
- 同一次請求裡的多個問題平行評估，多問幾題幾乎不增加延遲（speculative fan-out）
- 速率上限 1,200 requests／分鐘，單次 64k token（OpenRouter 為 32k）

官方 [Use case map](https://docs.typesafe.ai/concepts/use-case-map) 列出的五大類裡，「AI Map Reduce over Big Data」（成本低 100 倍）和「Scientific discovery」（篩選論文、標註訪談逐字稿、驗證引用、標出缺漏的方法細節、建立研究知識圖譜）正好交集在一個場景：**每天把整個科學文獻洪流讀一遍**。

以前這件事不划算：embedding 只能粗篩，LLM 讀全部太慢太貴，所以大家只能先用關鍵字或 embedding 砍到剩幾十篇，再用 LLM 看，被砍掉的就永遠看不到了。Jev 的成本結構讓「全部都判斷一次」第一次變得便宜。

### 1.2 痛點真實、持續、每天發生

- arXiv 2026 年 6 月單月收到 **32,040** 篇投稿，創歷史新高，且官方說成長「沒有放緩跡象」（[arXiv blog, 2026-07-09](https://blog.arxiv.org/2026/07/09/arxiv-now-hosts-over-3-million-articles/)）
- 換算每個公告日約 1,500 篇。沒有人讀得完，但每個研究者都怕漏掉關鍵論文

這是每天都會發生的需求，所以使用者會留下來，repo 也會持續有活動。

### 1.3 「Fork + GitHub Actions 每日論文推薦」這個模式已被驗證

搜尋 `zotero-arxiv-daily` 會看到滿滿一整頁使用者的 fork（例如 Archerll、augurier、CTRV12、zhough 等），證明這個模式會自然擴散：**每個使用者都要 fork 一份才能用**，所以每個使用者都變成公開可見的社群證明。

### 1.4 Jev 生態的空缺：大家都在做 coding agent 工具

Jev 上線才一週，生態已經很擁擠，但集中在同一塊：

| 觀察 | 來源 |
|---|---|
| awesome-typesafe-jev 已收錄 100+ 專案，432★、71 位貢獻者，今天仍在更新 | [AbdelStark/awesome-typesafe-jev](https://github.com/AbdelStark/awesome-typesafe-jev) |
| 高星專案：browser-use/jev-ultrafast 約 7.8k★、fast-jev-compaction 約 3.4k～4k★、SemIf（OpenJev）約 1.4k～1.8k★、jev-trader 約 1.2k★ | [awesome-jev-use-cases](https://github.com/walidboulanouar/awesome-jev-use-cases) 與各 repo 頁面（不同來源的快照數字略有出入） |
| Agent 路由、guardrail、compaction、semantic grep 各有 5～20 個同質專案 | 同上 |
| 科學類幾乎空白：jev-papers **0★**（一次性腳本，無每日流程）、typesafe-screening-mcp **1★**、1kpapers.com 是網站不是工具 | [jev-papers](https://github.com/normalnormie/jev-papers)、[typesafe-screening-mcp](https://github.com/masa-med-ai/typesafe-screening-mcp) |

「科學探索 × 大規模 map-reduce」是官方明列、社群卻還沒人做成**可 fork 即用產品**的空位。

### 1.5 從反例學到的事

[htlin222/meta-pipe #42](https://github.com/htlin222/meta-pipe/issues/42) 評估後**決定暫不**把 Jev 整合進系統性回顧的篩選流程，理由很有參考價值：

1. **規模太小**：一個系統性回顧只篩 100–750 篇，用 Jev 省下約 1 美元，不值得多一個供應商
2. **等候名單**：無法把研究基礎設施建在不確定的 API 上
3. **沒有文字理由**：PRISMA 需要記錄每筆排除的原因
4. **數字／日期推理弱**：納入條件常有「年齡 ≥ 18」「追蹤 ≥ 12 個月」
5. **沒有獨立校準驗證**：官方數據是自評

Paper Radar 的設計逐條回應：

| 疑慮 | 對策 |
|---|---|
| 規模太小 | 選「每天全量」場景：一天 1,500 篇、一年 30 萬篇，規模優勢才出得來 |
| 等候名單 | 內建 OpenRouter 後端（[不需排隊](https://jevaiguide.com/channels/openrouter/)），另有離線 mock 可試用 |
| 沒有文字理由 | 每個興趣是獨立的 Noul，頁面直接顯示「因為哪條興趣、機率多少」，本身就是結構化理由 |
| 數字／日期 | 從不讓模型比較數字或日期；`check` 會對含日期的興趣發出警告 |
| 無獨立驗證 | 內建 `calibrate`：用你自己的標註算 Brier score、ECE，並建議門檻 |

---

## 2. 目標使用者

| 族群 | 使用情境 | 為什麼會 star／fork |
|---|---|---|
| 研究生、博後、ML 工程師（主力） | 每天早上看自己領域的必讀清單 | GitHub 活躍，fork 才能用 |
| 實驗室 PI | 全實驗室共用一個 repo，每人一頁（路線圖：lab mode） | 一個 PI 帶來 5～20 個使用者 |
| 生醫研究者 | bioRxiv／medRxiv 每日篩選 | 目前幾乎沒有好用的工具 |
| 產業研究、投資、科技記者 | 「整個 arXiv 裡有沒有人用了 X 技術」 | 全量讀取是唯一解法 |
| 系統性回顧研究者 | 路線圖：screening mode | 學術圈口碑傳播 |

---

## 3. 產品設計（MVP 已完成）

### 3.1 流程

```
arXiv RSS / bioRxiv / 任意 RSS
  → 與最近 14 天去重
  → 每篇論文呼叫 Jev 一次（所有問題一起問）
  → 程式碼組合結果（max 或 noisy-OR、門檻、排除條件）
  → 網頁 + RSS + 通知 + data/ 審計紀錄
  → （選配）只對前 10 篇用 LLM 寫一句話摘要
```

### 3.2 每篇論文問 Jev 的問題

| 問題 | Primitive | 用途 |
|---|---|---|
| 每條興趣（白話一句） | Noul | 這篇符合此興趣的機率 |
| 每條排除條件（正面敘述） | Noul | 超過門檻就過濾掉 |
| 論文類型（9 類：新方法、benchmark、資料集、survey、理論…） | Choice | 頁面標籤 |
| 摘要是否說明釋出程式碼或資料 | Noul | 頁面標籤 |
| （選配）實驗證據多寡 | Score | 頁面訊號 |

傳給 Jev 的 state 只有標題、摘要、分類，**刻意不含作者與機構**。這遵循官方的「Retrieve then judge」原則，減少無關脈絡；也避免模型因作者名氣而產生偏差。

### 3.3 對應官方設計模式

- **Atomic questions**：一條興趣一個 Noul，組合邏輯寫在程式碼裡
- **Speculative fan-out**：同一篇的所有問題一次問完
- **Confidence-gated routing**：必讀／可能／差一點三個區段由門檻決定
- **Cascade**：Jev 負責從上千篇裡挑，LLM 只負責為入選的幾篇寫摘要
- **Jaggedness lint**：`paper-radar check` 會警告否定句、日期、and/or、過長的興趣

### 3.4 差異化重點

1. **真的讀完全部**：不先用 embedding 粗篩，所以不會漏掉「用詞不同但相關」的論文
2. **白話設定**：不用準備 Zotero 庫或訓練資料，寫幾句英文就能用
3. **可解釋**：每篇都顯示命中哪條興趣、機率多少
4. **可驗證**：`calibrate` 讓使用者自己測 Jev 準不準，這在整個 Jev 生態裡很少見
5. **零伺服器、零依賴**：只用 Python 標準函式庫，GitHub Actions 安裝只要幾秒；網頁放 GitHub Pages
6. **RSS 進 Zotero**：論文直接出現在研究者本來就在用的工具裡
7. **完整審計紀錄**：每個判斷、模型版本都 commit 進 repo，可重現

### 3.5 成本與速度（估算）

| 項目 | 估算 |
|---|---|
| 每篇 input tokens | 約 1,000（固定開銷約 250，參考官方範例一個短問題就計 296 token；問題約 350；標題與摘要約 400） |
| 全 arXiv 一天（約 1,500 篇） | 約 $0.06／天，約 $1.4／月 |
| 只看 cs.AI+CL+LG 等幾個分類（數百篇） | 每月幾毛錢 |
| 速度 | 速率設為 1,000 req／分鐘，1,500 篇約 1.5～2 分鐘 |
| GitHub Actions | 公開 repo 免費 |

以上是估算；每次執行的實際 token 與費用會寫進 `data/runs.jsonl`，網頁上也會顯示。

---

## 4. GitHub 爆紅策略

### 4.1 設計本身就會帶來擴散

- **每個使用者都是一個 fork**：fork 數公開可見，形成社群證明
- **每天自動 commit**：repo 持續有活動，GitHub 也不會因 60 天無活動而停用排程
- **個人網頁天生可分享**：「這是我的論文雷達」是很自然的貼文
- **`profiles/` 目錄**：各領域的人提交自己的設定檔 PR，貢獻者數量跟著成長，每個貢獻者也會幫忙宣傳

### 4.2 上線前一週

1. 用真實 API 金鑰跑 5 個工作日，確認 arXiv RSS 格式、成本與準確度
2. 錄一支 20 秒的影片，用**真實數字**：「Jev 花 N 秒、M 美分讀完今天 1,5xx 篇 arXiv，這是我該讀的 7 篇」
3. 開一個公開 demo 站：每天自動更新的「cs.AI 今日雷達」
4. 把 README 首圖換成真實資料的截圖
5. 發布到 PyPI，讓 `pipx run paper-radar demo` 一行就能試

### 4.3 發布日

- **X／Twitter**：tag @typesafeai。官方發表文邀請開發者回報使用情境，社群專案常被轉推
- **TypeSafe Discord** 的 Show and Tell 頻道
- **提 PR 到 8 個 awesome 清單**：AbdelStark/awesome-typesafe-jev、walidboulanouar/awesome-jev-use-cases、cobanov/awesome-jev、yibie/awesome-jev、Anil-matcha/awesome-jev-by-typesafe、AnotiaWang/awesome-jev、v-modal/awesome-jev-tools、awesomejev.com
- **Hacker News**：`Show HN: Paper Radar – Jev reads every new arXiv paper daily for ~6 cents`
- **Reddit**：r/MachineLearning（[P] 標籤）、r/bioinformatics（bioRxiv 角度）
- **中文社群**：知乎、V2EX、即刻、小紅書；台灣可用 Threads、PTT。README 已有英文與繁中版，可再補簡中

**時機很重要**：Jev 上線才一週，awesome 清單每天都在更新，現在正是熱度最高的窗口。

### 4.4 上線後 30 天

- **Good first issues**：PubMed 來源、Hugging Face Daily Papers 來源、LINE Messaging API 通知、更多領域 profile
- **每週「Radar Weekly」**：自動整理本週各領域熱門論文並發文，持續曝光
- **第二波話題：群眾外包的 Jev 獨立校準報告**。邀請使用者分享 `calibrate` 結果，彙整成「Jev 在 N 個學科的獨立校準評估」。Jev 目前最大的爭議就是缺乏獨立驗證（見 [KDnuggets](https://www.kdnuggets.com/what-everyone-is-getting-wrong-about-typesafe-ais-jev)），這份報告本身就有新聞價值

### 4.5 目標（是目標，不是預測）

| 時間 | Stars | Forks |
|---|---|---|
| 30 天 | 500 | 150 |
| 90 天 | 2,000 | 600 |

參考點：Jev 生態前幾名在上線一週內拿到 1k～8k★，但其中有公司背書的專案（browser-use）。

---

## 5. 路線圖

| 版本 | 內容 | 狀態 |
|---|---|---|
| v0.1 | arXiv／bioRxiv／RSS、TypeSafe／OpenRouter／mock 後端、網頁、RSS、Slack／Discord／Telegram／Email、LLM 摘要、calibrate、GitHub Actions | ✅ MVP 完成 |
| v0.2（2 週） | 網頁上一鍵 👍／👎（透過 GitHub Issues 收集標註）、PubMed、HF Daily Papers、PyPI 發布 | 規劃中 |
| v0.3（1 個月） | **Screening mode**：系統性回顧用，納入／排除條件各為 Noul，輸出 PRISMA 計數表，並支援與人工審查並行的 shadow mode | 規劃中 |
| v0.4 | **Lab mode**（一個 repo 多位成員）、必讀論文的引用驗證與缺漏方法標記、研究知識圖譜 | 規劃中 |
| v1.0 | 本地開源模型後端（完全離線）、資料改存到獨立分支以控制 repo 大小 | 規劃中 |

---

## 6. 風險與對策

| 風險 | 對策 |
|---|---|
| Jev 仍在 early access、可能改版或漲價 | 後端抽象化（TypeSafe／OpenRouter／mock）；固定 `model` 版本；價格是設定值 |
| 準確度未經獨立驗證 | `calibrate` 讓使用者自測；頁面標示「機率不是品質分數」 |
| 被綁定單一供應商 | 路線圖加入本地開源後端；問題格式與 System One 通用 |
| 摘要被刻意寫來操縱分類器 | 最壞情況只是清單裡多一篇不相關的；模型結果不會觸發任何動作 |
| arXiv RSS 格式變動 | 解析器容錯；來源失敗不會中斷整次執行；有測試夾具 |
| Repo 越來越大 | 未入選的論文只存精簡紀錄並 gzip；未來可改存獨立分支 |
| 成本失控 | `max_papers` 上限；`check` 事先估算；每次執行都記錄實際費用 |

---

## 7. 已驗證與尚未驗證

**已驗證**

- 66 個自動化測試全數通過：解析器、設定驗證、評分、HTTP 重試（429／529／retry-after）、致命錯誤中止、通知、摘要、calibrate、CLI
- HTTP 請求格式對照 TypeSafe 官方 Python SDK（`typesafe-sdk` 0.7.1，PyPI）的原始碼：路徑 `/v1/systemone`，body 為 `{model, state, questions}`，回應為 `{model, answers, usage}`
- OpenRouter 格式對照其 [Decisions API 文件](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request)（多一個 `usage.cost`，程式已支援）
- 離線 demo 可產生完整網站，亮色與暗色、手機與桌面版面都檢查過

**尚未驗證（需要你的金鑰與網路）**

- 真實 Jev API 的端到端呼叫（沙盒無法連到 TypeSafe 與 arXiv）
- arXiv RSS 的實際格式：解析器依照 arXiv 2024 年起的新 RSS 格式撰寫，並有容錯，但要用真實 feed 確認一次
- 真實的每篇 token 數與分類品質

---

## 8. 你的下一步

1. 在 GitHub 建立 `paper-radar` repo，把 `OWNER` 換成你的帳號（`paper_radar/__init__.py`、`pyproject.toml`、兩份 README）。把 `github-workflows/` 裡的兩個檔案移到 `.github/workflows/`（遠端工具無法直接寫入 `.github` 資料夾）
2. 取得 `TYPESAFE_API_KEY`，或先用 OpenRouter
3. 本機執行 `paper-radar check`，再執行 `paper-radar run --limit 50`，確認真實 API 與 RSS 都正常
4. 把 `radar.toml` 改成你自己的研究興趣，跑一週、標註約 30 篇，再用 `calibrate` 調整門檻
5. 依第 4 節的發布計畫上線
