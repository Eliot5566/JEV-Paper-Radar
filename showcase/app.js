"use strict";

const zh = {
  skip: "跳至主要內容", navStart: "開始使用", navFeeds: "公開 Jev 論文雷達",
  eyebrow: "研究日常，少一點整理工作", headline: "讀少一點。<br>每篇都有理由。",
  lead: "寫下研究興趣，或貼上論文連結。技能取得公開標題與摘要，再由目前的 Claude 對話排序，留下理由與可繼續使用的檔案。",
  preview: "先看一份報告 ↗", install: "在 Claude 裡使用",
  fine: "MIT 開源授權 · 對話模式不需額外 API 金鑰 · 仍使用 Claude 方案額度",
  previewCaption: "對話內產生的報告", fictional: "虛構範例", interestLabel: "研究興趣",
  interest: "工具型 LLM agent 的評測基準", abstracts: "篇摘要", shortlisted: "篇入選", all: "全部 3 篇", picks: "只看入選",
  mustRead: "必讀", skipBand: "略過", reasonOne: "提出多步工具呼叫與工具失敗復原的評測基準。",
  reasonTwo: "研究推論效率，並非 agent 評測基準。", reasonThree: "影像分類研究，與設定的興趣無關。",
  previewNote: "這些是實際功能驗收使用的虛構論文。分數由 Claude 自述，未經校準；不同對話可能給出不同分數。",
  chooseEyebrow: "選擇適合你的起點", chooseTitle: "先看看，再變成自己的工具。",
  lookTitle: "先看成品", lookText: "瀏覽 44 篇論文的離線示範，或三篇摘要的對話報告。閱讀這些範例不需安裝或金鑰。",
  lookLink: "瀏覽離線示範 →", reportLink: "查看對話報告 →",
  claudeTitle: "從興趣或連結開始", claudeText: "上傳啟用 0.2.0，提供研究興趣或 arXiv／PubMed／DOI 連結。取得公開資料後由對話排序，需要允許連線或既有 Claude 網頁工具。",
  claudeLink: "安裝技能、取得提示詞 →", dailyTitle: "每天追蹤一個領域",
  dailyText: "直接訂閱現有的公開 Jev 雷達，或設定自己的每日 API 工作流程。排程與額外 API 判斷需要另外設定。",
  dailyLink: "閱讀公開 Jev 雷達 →", workflowLink: "Fork Claude API 範例 →",
  startEyebrow: "從下載到第一份結果", startTitle: "第一份閱讀清單，<br>從一個興趣開始。",
  stepOneTitle: "下載完整技能 ZIP。", stepOneText: "請使用 paper-radar-claude-v0.2.0.zip，不是專案的 Source code ZIP。",
  stepTwoTitle: "Claude → 自訂 → Skills 上傳。", stepTwoText: "啟用 paper-radar 與程式執行／檔案建立功能；組織管理員可能限制這些功能。",
  stepThreeTitle: "新開對話，貼上右側提示詞。", stepThreeText: "可先試虛構示範，再提供興趣或論文連結；CSV 不是必要步驟。",
  download: "下載 Claude 技能 ZIP ↓", fullGuide: "閱讀完整安裝教學", demoTab: "先跑示範", findTab: "幫我找論文", ownTab: "連結／摘要", linksLabel: "論文連結（選填：arXiv、PubMed 或 DOI）",
  fieldLabel: "一個明確的研究興趣", presetAgents: "Agent 評測", presetEfficiency: "高效率推論", presetNeuro: "神經科學",
  promptLabel: "複製到 CLAUDE", copy: "複製提示詞", openClaude: "開啟 Claude ↗",
  sampleCsv: "下載三篇虛構摘要 CSV", blankCsv: "下載空白 CSV 範本",
  builderNote: "本頁只整理提示詞，不會傳送資料。在 Claude 檢索時，搜尋詞或論文 ID 會傳給公開來源或允許使用的網頁工具；缺摘要與失敗會列出。",
  outputsEyebrow: "留下結果，不只留下對話", outputsTitle: "一份閱讀清單，四種實用檔案。",
  htmlTitle: "閱讀頁面", htmlText: "分數、理由與摘要，放在一起。", csvTitle: "工作表格", csvText: "放進試算表，繼續標註與比較。",
  jsonTitle: "可追溯紀錄", jsonText: "保留 ID、分數與輸入來源。", rssTitle: "可發布的訂閱源", rssText: "匯出入選論文，再部署到固定網址。",
  outputsNote: "以上連結是固定的虛構範例。你自己的 HTML、CSV、JSON 會保留全部輸入論文；RSS 只包含入選內容。",
  faqEyebrow: "第一次執行前", faqTitle: "先了解工具能做什麼。",
  q1: "需要 API 金鑰嗎？", a1: "對話內檢索、排序、匯出不需額外模型 API 金鑰，仍使用 Claude 方案額度。檢索需要可用網路或既有網頁工具，會發出公開資料請求；每日 API 自動化另計費。",
  q2: "安裝後就會每天自動執行嗎？", a2: "不會。上傳技能用於目前的對話；可在對話中要求單次檢索；每日排程、長期保存與公開發布仍需另外設定本機或 GitHub Actions 工作流程。",
  q3: "0.93 就代表有 93% 機率相關嗎？", a3: "不是。Claude 分數是自述的，未經校準。請親自標註入選與未入選論文，用一批資料調門檻，再以之後分開標註的一批檢查結果。",
  q4: "目前實際驗證過什麼？", a4: "已在 Claude 網頁版 Opus 5.5 載入技能、核對檔案並匯出報告。0.2.0 連結測試遇到 API 網路限制後，改用既有網頁工具取得兩篇真實論文，改寫摘要明確標示。本機 249 項測試與 Python 3.11–3.13 CI 通過；這些是功能驗收，不是準確率或所有客戶端相容性保證。",
  q5: "遇到問題，要提供什麼回饋？", a5: "提供環境、版本、卡住的步驟與遮蔽敏感資訊後的錯誤。不要貼金鑰、私人摘要或未公開研究。第一次使用的具體經驗，比 star 更能幫助改善工具。",
  feedbackEyebrow: "一起決定下一版的優先順序", feedbackTitle: "第一次使用，卡在哪裡？",
  feedbackText: "告訴我們你的領域、先試了哪一步，以及一件沒有成功的事。具體經驗能幫助我們改進。",
  feedbackButton: "回報首次使用經驗 →", footer: "獨立的 MIT 開源專案，與 Anthropic 無隸屬關係。本頁沒有分析追蹤、模型呼叫或檔案上傳。", docsLink: "文件"
};

const english = Object.fromEntries([...document.querySelectorAll("[data-i18n]")].map(el => [el.dataset.i18n, el.innerHTML]));
const richKeys = new Set(["headline", "startTitle", "preview"]);
const languageButton = document.getElementById("language");
const prompt = document.getElementById("prompt");
const interestInput = document.getElementById("research-interest");
const status = document.getElementById("copy-status");
const linksInput = document.getElementById("paper-links");
let language = new URLSearchParams(location.search).get("lang") === "zh" ? "zh" : "en";
let mode = "demo";
const presets = {
  agents: "Benchmarks for evaluating tool-using LLM agents",
  efficiency: "Methods for reducing language-model inference memory usage",
  neuro: "Neural mechanisms of memory consolidation during sleep"
};

function updatePrompt() {
  const interest = interestInput.value.trim() || presets.agents;
  if (mode === "demo") {
    prompt.value = language === "zh"
      ? "使用 paper-radar 技能跑內附離線示範，不安裝套件、不連網、不要求 API 金鑰。請提供 HTML 與 RSS，確認示範紀錄數，並明示論文是虛構、分數來自關鍵字規則。"
      : "Use the paper-radar skill to run its bundled offline demo. Do not install packages, use network access or request an API key. Provide HTML and RSS, confirm the record count, and state that the papers are fictional and scores come from keyword rules.";
  } else if (mode === "find") {
    prompt.value = language === "zh"
      ? `使用 paper-radar 技能，依我的研究興趣找論文：${interest}。請自行從 arXiv 或 PubMed 取得最近 30 天最多 10 篇候選論文的標題摘要，列出查詢、來源、日期範圍及失敗項目；再由目前對話排序，保留全部取得的 ID 與低分項目，輸出 HTML、CSV、JSON、RSS。不要求我整理 CSV、不使用額外模型 API。保留來源與缺摘要紀錄，分數未校準；網路不可用時明示限制。`
      : `Use paper-radar to find papers for this interest: ${interest}. Retrieve up to 10 candidates from the last 30 days using arXiv or PubMed. Show the query, source, date window and failures. Rank in this conversation and export HTML, CSV, JSON and RSS, preserving all retrieved IDs and low scores. Do not ask me to prepare CSV or call a separate model API. Preserve provenance and missing-abstract records; scores are uncalibrated. Disclose network limitations.`;
  } else {
    const links = linksInput.value.trim();
    prompt.value = language === "zh"
      ? `使用 paper-radar 技能，依研究興趣「${interest}」處理${links ? "以下論文連結，自行取得標題與摘要：\n" + links : "我附上或貼上的標題與摘要"}。\n\n在目前對話評分，保留全部取得的 ID、低分項目、簡短理由與來源，輸出 HTML、CSV、JSON、RSS。不使用額外模型 API。缺摘要或連線失敗請列出；若是改寫摘要須標示。分數未校準，對話用量與費用未知。若沒有連結或摘要，請先向我索取。`
      : `Use paper-radar for this interest: ${interest}. Process ${links ? "these paper links and retrieve their titles and abstracts:\n" + links : "the titles and abstracts I attached or pasted"}.\n\nScore in this conversation and export HTML, CSV, JSON and RSS. Preserve all retrieved IDs, low scores, reasons and provenance. No separate model API calls. Disclose missing abstracts, network failures and any paraphrases. Scores are uncalibrated; chat usage and cost are unknown. Ask for links or abstracts if none were supplied.`;
  }
  status.textContent = "";
}

function setLanguage(next) {
  language = next;
  const dictionary = language === "zh" ? zh : english;
  document.documentElement.lang = language === "zh" ? "zh-Hant" : "en";
  document.title = language === "zh" ? "Paper Radar · 找到下一篇值得讀的論文" : "Paper Radar · Find your next paper";
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const value = dictionary[el.dataset.i18n];
    if (value === undefined) return;
    if (richKeys.has(el.dataset.i18n)) el.innerHTML = value;
    else el.textContent = value;
  });
  languageButton.textContent = language === "zh" ? "English" : "繁體中文";
  languageButton.setAttribute("aria-label", language === "zh" ? "Switch to English" : "切換為繁體中文");
  updatePrompt();
}

function setMode(next) {
  mode = next;
  for (const value of ["demo", "find", "own"]) {
    const button = document.getElementById(`mode-${value}`);
    button.classList.toggle("selected", mode === value);
    button.setAttribute("aria-pressed", String(mode === value));
  }
  document.getElementById("interest-field").hidden = mode === "demo";
  document.getElementById("links-field").hidden = mode !== "own";
  updatePrompt();
}

languageButton.addEventListener("click", () => {
  const next = language === "en" ? "zh" : "en";
  const url = new URL(location.href);
  url.searchParams.set("lang", next);
  history.replaceState(null, "", url);
  setLanguage(next);
});
for (const value of ["demo", "find", "own"]) document.getElementById(`mode-${value}`).addEventListener("click", () => setMode(value));
interestInput.addEventListener("input", updatePrompt);
linksInput.addEventListener("input", updatePrompt);
document.querySelectorAll("[data-preset]").forEach(button => button.addEventListener("click", () => {
  interestInput.value = presets[button.dataset.preset];
  updatePrompt();
}));
document.getElementById("copy-prompt").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(prompt.value);
    status.textContent = language === "zh" ? "已複製。到 Claude 貼上即可。" : "Copied. Paste it into Claude.";
  } catch {
    prompt.focus();
    prompt.select();
    status.textContent = language === "zh" ? "已選取提示詞，請按 Ctrl+C 或 ⌘C 複製。" : "Prompt selected. Press Ctrl+C or ⌘C to copy.";
  }
});
for (const [id, onlyPicks] of [["show-all", false], ["show-picks", true]]) {
  document.getElementById(id).addEventListener("click", () => {
    document.querySelectorAll(".other-paper").forEach(card => { card.hidden = onlyPicks; });
    for (const [buttonId, active] of [["show-all", !onlyPicks], ["show-picks", onlyPicks]]) {
      const button = document.getElementById(buttonId);
      button.classList.toggle("selected", active);
      button.setAttribute("aria-pressed", String(active));
    }
  });
}
setLanguage(language);
