# 發布清單：怎麼讓 Paper Radar 被看見

星星來自三件事的乘積：**東西有用 × 有人看到 × 一眼就相信它能動**。第三點最常被忽略——大部分 repo 死在「看起來不錯，但我不確定它真的會跑」。

時機上，Jev 在 2026-09-15 上線，awesome 清單每天都在更新，這個窗口大概只有兩三週。

---

## 第 0 層：發布前一定要做（約 1 小時）

沒做完這層就去宣傳，流量會白白流掉。

### 1. repo 外觀（5 分鐘，影響最大的 5 分鐘）

到 repo 首頁右上角齒輪（About）填：

- **Description**：
  `Let Jev read every new arXiv paper each morning and surface the few you should read. Plain-English interests, calibrated probabilities, ~$0.06/day, fork and go.`
- **Website**：`https://eliot5566.github.io/JEV-Paper-Radar/`
- **Topics**（GitHub 搜尋和推薦都吃這個）：
  `jev` `typesafe` `system-one` `arxiv` `research-tools` `paper-recommendation` `literature-review` `github-actions` `rss` `llm` `python` `biorxiv`

### 2. 首圖與首屏（已完成）

- README 第一眼就是真實執行的截圖 + 真實數字（5 秒 / $0.002 / 50 篇）✅
- 表格用「讀完全部 vs 只讀 top-k」當賣點 ✅

### 3. 降低第一道門檻

訪客最常卡在「我沒有 TypeSafe 金鑰」。README 的 Quick start 已經同時給了 OpenRouter（免排隊）和 `paper-radar demo`（免金鑰）。宣傳文案裡也要提一句，不然一半的人會直接關掉。

### 4. 一支 20～30 秒的錄影

比任何文字都有效。錄製內容：

1. 終端機跑 `paper-radar run`，畫面上跑完 N 篇
2. 切到瀏覽器，顯示漏斗數字（讀 N 篇 → 入選 M → 必讀 K、花費 $0.0x）
3. 捲過必讀清單，秀出每篇的「命中哪條興趣、機率多少」

用 ScreenToGif 或 Windows 內建的錄影都可以，輸出 GIF 放進 README 首圖下方。

---

## 第 1 層：發布日（集中在同一天，效果會疊加）

### awesome 清單 PR（最高投報率）

Jev 生態的 awesome 清單正在密集更新，收錄門檻低、流量真實。一次發 8 個 PR：

| repo | 放在哪一節 |
|---|---|
| AbdelStark/awesome-typesafe-jev | Applications & Workflows |
| walidboulanouar/awesome-jev-use-cases | Research & Data |
| cobanov/awesome-jev | Projects |
| yibie/awesome-jev | Projects |
| Anil-matcha/awesome-jev-by-typesafe | Use cases |
| AnotiaWang/awesome-jev | Applications |
| v-modal/awesome-jev-tools | Tools |
| awesomejev.com | 用站上的 Suggest 表單 |

PR 內容一行就好：

```
- [Paper Radar](https://github.com/Eliot5566/JEV-Paper-Radar) — Reads every new arXiv/bioRxiv paper each morning against plain-English interests and publishes a daily page + RSS. 50 papers in 5s for $0.002; all of arXiv ≈ $0.06/day. Fork-and-go GitHub Action, zero dependencies.
```

### Hacker News

- 標題：`Show HN: Paper Radar – Jev reads every new arXiv paper daily for ~6 cents`
- 送出時間：台灣時間 21:00～23:00（美西早上）
- 第一則留言由自己補上：為什麼不用 embedding 預篩、成本怎麼算出來的、Jev 的限制（照字面讀、不會算數）、以及 `calibrate` 為什麼存在

誠實講限制反而加分，HN 讀者對誇大非常敏感。

### X / Twitter

一則帶影片的貼文，tag `@typesafeai`（官方在發表文裡邀請開發者回報使用情境，社群專案常被轉推）：

```
Jev read all of today's new arXiv papers in my fields and picked the 4 I should actually read.

5 seconds. $0.002. Nothing pre-filtered by embeddings — every paper gets judged.

Fork the repo, write your interests in plain English, add a key. Runs on GitHub Actions, publishes a page + RSS.
```

### Reddit

- r/MachineLearning，標題前綴 `[P]`
- r/bioinformatics（主打 bioRxiv / medRxiv 那條線）
- 兩邊都要遵守版規：先講做了什麼、怎麼做的、限制是什麼，連結放最後

### TypeSafe Discord

`show-and-tell` 頻道貼影片 + 連結。官方團隊會看，被官方轉推一次抵過幾十則自己的貼文。

### 中文社群

知乎、V2EX、即刻、小紅書；台灣可用 Threads。README 已有英文與繁中，可再補一份簡中版。

---

## 第 2 層：發布後 30 天（維持熱度）

- **good first issues**：PubMed 來源、Hugging Face Daily Papers 來源、LINE 通知、各領域 profile。標好 `good first issue`，貢獻者會自己找上門，每個貢獻者也會幫忙宣傳
- **profiles/ 徵集**：發一則「把你的領域設定檔 PR 上來」，門檻低、參與感高
- **Radar Weekly**：每週整理一次本週各領域的熱門論文並發文，持續曝光
- **第二波話題：群眾外包的 Jev 獨立校準報告**。邀請使用者分享 `paper-radar calibrate` 的結果，彙整成「Jev 在 N 個學科上的獨立校準評估」。Jev 目前最大的爭議就是官方數據沒有第三方驗證，這份報告本身就有新聞價值，而且只有這個專案做得出來

---

## 還沒做但值得做的兩件事

1. **公開的 demo radar**：每天自動更新一頁「cs.AI 今日雷達」，讓沒有金鑰的訪客直接看到價值。這是轉換率最高的資產，也是社群媒體每天可以貼的素材。
2. **一鍵 👍/👎**：頁面上的按鈕開一個預填的 GitHub Issue，自動收集標註餵給 `calibrate`。這讓「校準到你自己」從功能變成習慣。

---

## 怎麼衡量

- **fork 數比星數更能反映真實使用**（每個使用者都必須 fork 才能用）
- 前 48 小時的星數成長曲線決定後續能不能進 GitHub Trending
- 真正的成功指標是一週後還在每天自動跑的 fork 數量
