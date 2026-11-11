# Claude calibration: a first look (2026-11-11)

> **Read this first — provenance.** The labels in this document were made by
> **Muse (the assistant), not by the user.** The user said they are not
> familiar enough with agent evaluation, LLM calibration, or RAG & retrieval
> to label the papers themselves, and asked Muse to label them. Each label was
> judged from the paper's title plus a trimmed abstract (~2 sentences) against
> the three interest texts in `radar.toml`. Jev judgments were **not** used as
> proxy labels. This is a **first-look calibration, not a user-validated one**:
> n = 49 papers with only 6 positives, one day, one batch. Do not present
> these numbers as the user's own calibration, and do not claim Claude is
> "calibrated" — the expected calibration error (0.081) is above the 0.05 bar
> the `calibrate` command itself calls well calibrated. The right use of this
> page is as a starting point: if you run the Claude backend, label your own
> papers and re-fit the thresholds with `paper-radar calibrate`.

## What ran

- **Date:** 2026-11-11 arXiv announcement.
- **Config:** a copy of the repo's `radar.toml` with only the backend changed:
  `[jev] backend = "claude"`, `model = "claude-haiku-5-5"`,
  `price_per_mtok = 0.15`. Same sources (arXiv cs.AI, cs.CL, cs.LG, cs.IR,
  stat.ML, cross-lists included), same three interests — agent evaluation
  ("Benchmarks or methods for evaluating LLM agents on multi-step tool-use
  tasks"), LLM calibration, RAG & retrieval — same exclusions, and the Jev
  thresholds in `radar.toml` at the time (`must_read = 0.80`,
  `maybe = 0.50`).
- **Command:** `paper-radar run -c radar.toml --backend claude --limit 50
  --no-notify`, run in an isolated directory so the daily Jev radar's
  `data/` was untouched.
- **Batch:** 478 papers fetched, first 50 judged. **49 judged, 1 failed.**
  Bands: 4 must-read, 2 maybe, 42 skip, 1 excluded.
- **Cost and time:** 50,125 input tokens (~1,023 per paper), **$0.0075**
  (Haiku at $0.15/MTok input), 53.1 seconds.
- **Scores:** relevance spans 0.02–0.93 across 18 distinct values; no paper
  scored exactly 0 or 1, so the scores look like graded probabilities rather
  than yes/no flips. 32 of 49 papers scored below 0.10, and all 32 were
  labelled not relevant.

## One failure

`arxiv:2611.12959` produced no decision: Claude returned a non-numeric value
for the agent-evaluation interest (`'i_agent_eval' noul must be a number in
[0, 1]`), which the response validation rejected. That is 1 in 50 papers
(~2%) failing validation on the first pass. The CLI reports it as failed and
retries it on the next run. A Claude deployment should expect a small
validation-failure rate like this and handle it (retry), rather than assuming
every response parses.

## Results

`paper-radar calibrate` on the 49 labelled papers (6 relevant):

- **Labelled papers: 49 (6 relevant)**
- **Brier score: 0.040** (0 is perfect; 0.25 is a coin flip)
- **Expected calibration error: 0.081** (lower is better; < 0.05 is well
  calibrated — **this is above that bar**)

| thresh | flagged | precision | recall |
|-------:|--------:|----------:|-------:|
| 0.05 | 24 | 0.25 | 1.00 |
| 0.10 | 17 | 0.35 | 1.00 |
| 0.15 | 15 | 0.40 | 1.00 |
| 0.20 | 15 | 0.40 | 1.00 |
| 0.25 | 15 | 0.40 | 1.00 |
| 0.30 | 12 | 0.50 | 1.00 |
| 0.35 | 9 | 0.67 | 1.00 |
| 0.40 | 7 | 0.71 | 0.83 |
| 0.45 | 7 | 0.71 | 0.83 |
| 0.50 | 6 | 0.83 | 0.83 |
| 0.55 | 6 | 0.83 | 0.83 |
| 0.60 | 6 | 0.83 | 0.83 |
| 0.65 | 4 | 1.00 | 0.67 |
| 0.70 | 4 | 1.00 | 0.67 |
| 0.75 | 4 | 1.00 | 0.67 |
| 0.80 | 4 | 1.00 | 0.67 |
| 0.85 | 3 | 1.00 | 0.50 |
| 0.90 | 1 | 1.00 | 0.17 |
| 0.95 | 0 | 1.00 | 0.00 |

### Suggested Claude thresholds (first look only)

- **Suggested must_read: 0.65** (precision ≥ 90% — on this set, the 4 papers
  at or above 0.65 were all relevant, 4 of 6 positives found).
- **Suggested maybe: 0.35** (recall ≥ 90% — on this set, 0.35 is the lowest
  threshold that keeps recall at 1.00; the 9 flagged papers include all 6
  relevant ones).

For comparison, the current Jev thresholds in `radar.toml`, applied to
Claude's numbers on this labelled set:

- **must_read 0.80:** precision 1.00, recall 0.67 — clean at the top, but
  misses 2 of 6 relevant papers.
- **maybe 0.50:** precision 0.83, recall 0.83 — 5 of 6 relevant papers, with
  one false positive.

### What this does and does not show

- The top end is sharp: all 4 papers Claude scored ≥ 0.80 were relevant, and
  the two papers at 0.60 split — one relevant (DocFS, 2611.12957), one not
  (ChipOmni, 2611.13020). The one relevant paper Claude scored low was
  IntentTwin (2611.12918, 0.35), an offline web-behavior paper whose
  relevance to agent evaluation is genuinely borderline — that single paper
  is what forces the suggested `maybe` threshold down to 0.35.
- The low Brier score (0.040) is mostly the 43 negatives: with so few
  positives, a model that says "probably not" almost everywhere scores well
  on Brier while still being imperfectly calibrated (ECE 0.081). Read the
  precision/recall table, not the Brier score alone.
- **Do not apply these thresholds to Jev, and do not apply the Jev
  thresholds (0.80 / 0.50) to Claude without re-fitting.** They belong to the
  backend that produced the numbers. `paper-radar calibrate` says the same
  when the backend is Claude.

## The 6 relevant papers

| arXiv id | Claude relevance | Title |
|---|---|---:|
| 2611.12966 | 0.93 | BuySideFlow: A Point-in-Time Benchmark for LLM Agents in Investment Research |
| 2611.12934 | 0.85 | EarthRecord: From Pixels to Land Change with Multimodal Agents over Four Decades of Satellite Imagery |
| 2611.13015 | 0.85 | From Questions to Decisions: Benchmarking How LLM Agents Acquire Decision-Relevant Information from Human Beings |
| 2611.12953 | 0.80 | Agent Architecture Cost-Success Trade-offs: A Controlled Evaluation across Enterprise-Style SOPs |
| 2611.12957 | 0.60 | DocFS: File Systems as Agentic Reasoning Environments for Complex Multimodal Document Question Answering |
| 2611.12918 | 0.35 | IntentTwin: Deconfounding Candidate Support and the Oracle-to-Deployment Gap in Offline Web Behavior Prediction |

## Full label table (49 papers)

Claude relevance is the stored decision from the batch; the label is the
Muse-made yes/no described at the top. Sorted by Claude relevance,
highest first.

| arXiv id | Claude relevance | Claude band | Label relevant? | Title |
|---|---|---|:---:|---|
| 2611.12966 | 0.93 | must_read | yes | BuySideFlow: A Point-in-Time Benchmark for LLM Agents in Investment Research |
| 2611.12934 | 0.85 | must_read | yes | EarthRecord: From Pixels to Land Change with Multimodal Agents over Four Decades of Satellite Imagery |
| 2611.13015 | 0.85 | must_read | yes | From Questions to Decisions: Benchmarking How LLM Agents Acquire Decision-Relevant Information from Human Beings |
| 2611.12953 | 0.80 | must_read | yes | Agent Architecture Cost-Success Trade-offs: A Controlled Evaluation across Enterprise-Style SOPs |
| 2611.12957 | 0.60 | maybe | yes | DocFS: File Systems as Agentic Reasoning Environments for Complex Multimodal Document Question Answering |
| 2611.13020 | 0.60 | maybe | no | ChipOmni: A General-Purpose AI Agent for Electronic Design Automation |
| 2611.12900 | 0.49 | skip | no | From Relevant Posts to Attributable Spans: Explicit Symptom Evidence for Depression Questionnaire Inference |
| 2611.12903 | 0.36 | skip | no | SELD: Detecting Silent Evidence Loss in Context Compression beyond the Answer |
| 2611.12918 | 0.35 | skip | yes | IntentTwin: Deconfounding Candidate Support and the Oracle-to-Deployment Gap in Offline Web Behavior Prediction |
| 2611.12938 | 0.32 | skip | no | Graph Visualizations in Prompts for Knowledge Graph Question Answering |
| 2611.12933 | 0.30 | skip | no | Auditable Human-Agent Teams for Autonomous X-ray Experimentation |
| 2611.12970 | 0.30 | skip | no | TrustMod-SM: A Multi-Axis Benchmark for Evaluating Trustworthiness of LLMs in Social Media Content Moderation |
| 2611.12958 | 0.25 | skip | no | Embodied Science Agents: Making Embodied Experimental Design Learnable |
| 2611.12990 | 0.25 | skip | no | Multimodal Graph Learning: A Survey of Models, Benchmarks, and Frontiers |
| 2611.13006 | 0.25 | excluded | no | Seeing Is Not Believing: Counterfactual Lesion Erasure Teaches a Small Medical Vision-Language Agent to Report Only What the Image Shows |
| 2611.12941 | 0.12 | skip | no | AI Governance Should Prioritize Control and Knowledge Boundaries Over Limiting Intelligence |
| 2611.12942 | 0.12 | skip | no | Tabular Foundation Models vs Tuned Gradient Boosting for Telecom Churn: A Profit- and Calibration-Aware Evaluation |
| 2611.12992 | 0.08 | skip | no | ZeroPoint: Lightweight Energy-Based Decision Model |
| 2611.12956 | 0.07 | skip | no | ADIndex: Layer-Adaptive Sparse Attention Indexing via Group-Level Distillation |
| 2611.12901 | 0.05 | skip | no | Rethinking in Spikes: Mitigating Hallucinations in MDLMs with Step-Aware Decoding |
| 2611.12906 | 0.05 | skip | no | Brasilidade: Measuring Brazilian Identity for Large Language Models |
| 2611.12937 | 0.05 | skip | no | Tracing Psychometric Inference in Large Language Models |
| 2611.12988 | 0.05 | skip | no | Third Eye: Beyond Immediate Gains in Recursive Self-Improvement |
| 2611.13003 | 0.05 | skip | no | Branch-and-Commit for Frozen RL Agents: When and Where to Spend Test-Time Compute |
| 2611.12935 | 0.04 | skip | no | Train on prefill, monitor at decode: Using sparse autoencoders for topic monitoring |
| 2611.12998 | 0.04 | skip | no | Linear Probes to Bayesian Manifolds: Geometry of Arithmetic in Large Language Models |
| 2611.13024 | 0.04 | skip | no | GRAP: Gender Rubric-Aware Probing for Analyzing Gender Bias in LLMs |
| 2611.12902 | 0.03 | skip | no | TimeOmni-o1: Bidirectionally Coupling Time Series Foundation Models and LLMs for Multimodal Reasoning and Forecasting |
| 2611.12904 | 0.03 | skip | no | Actionable Feedback: Improving Model Capabilities from User Edit Data on Clinical Documentation |
| 2611.12950 | 0.03 | skip | no | SetPrint: Black-Box LLM Fingerprinting via Setwise Correspondence of Response Changes |
| 2611.12955 | 0.03 | skip | no | Predictive Surprise as Self-Grounding Concept Bottleneck for Interpretable Time Series |
| 2611.12961 | 0.03 | skip | no | RBLA+: Efficient Rank-Specific LoRA Adapter Extraction for Federated Fine-Tuning with Heterogeneous Clients |
| 2611.12974 | 0.03 | skip | no | StatPrompt-LLM: A Lightweight Statistical Refinement for Foundation-Style Time-Series Forecasting |
| 2611.12995 | 0.03 | skip | no | Capacity Allocation at the Source: Sparse Target Optimization for LLM Knowledge Editing |
| 2611.13001 | 0.03 | skip | no | One Table, Many Queries: Benchmarking Generalist Tabular Models Across Generation, Imputation, and Prediction |
| 2611.13005 | 0.03 | skip | no | The Shape of a Program: Path Signatures for Trace-to-Program Induction |
| 2611.13016 | 0.03 | skip | no | Permutation-Based Pre-trained Model Merging via Reciprocal Orthogonality |
| 2611.13017 | 0.03 | skip | no | Multi-Future Drafting: Mixture Block Drafters for Tree-Verified Speculative Decoding |
| 2611.13022 | 0.03 | skip | no | Understanding-First AI Engineering: Purposes, Reference Architecture, and Architectural Patterns for Human Understanding |
| 2611.12936 | 0.03 | skip | no | LandslideFM: A Foundation Model Towards Unified Landslide Perception and Understanding |
| 2611.12927 | 0.02 | skip | no | An ensemble of graph generative models for assisted history matching of the Brugge field case |
| 2611.12940 | 0.02 | skip | no | Reinforcement Learning based control of Cancer Chemotherapy treatments |
| 2611.12954 | 0.02 | skip | no | Physics2Weight: Direct Neural Network Architecture and Weight Generation from Physical Laws Using Large Language Models |
| 2611.12960 | 0.02 | skip | no | IIT Patna at "ICPR 2026 TVRID Competition on Privacy-Preserving Person Re-Identification from Top-View RGB-Depth Camera" |
| 2611.12964 | 0.02 | skip | no | Exploration via Exploitation: The Blessing of Reward Diversity in Personalized Federated RL |
| 2611.12980 | 0.02 | skip | no | MADSNet: A Multi-Scale Axial-Attentive Dense Spiking Network for Spike Camera Image Reconstruction |
| 2611.13012 | 0.02 | skip | no | khammoon: From a Linguistic Guideline to a Thai Morpheme Segmenter |
| 2611.13013 | 0.02 | skip | no | FaST: Factored Synthesis of Transitions for Offline Reinforcement Learning |
| 2611.13030 | 0.02 | skip | no | APS-VLA: Action-Guided and Future-Aware Token Pruning for Efficient Vision-Language-Action Models |

## How this compares with Jev

The "not user-validated" warning at the top should not be read as "Jev was
validated and Claude was not". The user never labelled papers for Jev
either:

- `data/labels.jsonl` has never existed in this repo: `git log --all --
  data/labels.jsonl` is empty, and no file matching `*label*` has ever been
  tracked.
- The Jev thresholds in `radar.toml` (`must_read = 0.80`, `maybe = 0.50`)
  are defaults from the repo's very first commit (`5cff762`, 2026-09-28),
  whose comment says to "tune these with `paper-radar calibrate` after
  labelling ~30 papers" — a step that was never taken.
- Jev's "calibrated probabilities" is TypeSafe's own model claim. The
  README says TypeSafe's accuracy and calibration figures are
  self-reported and that its benchmark numbers "have not been reproduced
  independently" — they were never measured on this daily radar.
- The only ground-truth measurement in the repo is the screening benchmark
  (`benchmarks/clef_tar_2019/`), judged against Cochrane reviewers'
  decisions under a pre-registration — screening mode, Jev-only.

So this page is the first labelled measurement for either backend on the
daily arXiv radar. That does not make it user-validated — the caveat at the
top still stands — but Jev and Claude start from the same place here:
neither has ever been checked against this user's own labels.

## Limitations

- **Labels are Muse's, not the user's.** The user is not familiar enough
  with agent evaluation, LLM calibration, or RAG & retrieval to label these
  papers, and asked Muse to do it. The labels reflect one assistant's
  reading of titles and trimmed abstracts against the three interest texts —
  not the user's judgment, and not an expert panel's.
- **Thin evidence.** 49 papers, 6 positives, one day, one batch. One paper
  (IntentTwin at 0.35) moves the suggested `maybe` threshold on its own;
  with so few positives, every threshold here is fragile. A second batch, or
  labels from the actual user, could move them.
- **Trimmed abstracts.** Labels were judged from titles plus ~2 sentences of
  abstract, not full papers. A paper whose relevance only shows in the
  methods section may have been mislabelled.
- **Single model, single day.** `claude-haiku-5-5` on the 2026-11-11 arXiv
  listing only. Other Claude models, other days, and other interest sets
  will differ.
- **Not calibrated.** ECE 0.081 is above the 0.05 well-calibrated bar. These
  numbers describe how Claude's self-reported probabilities lined up against
  Muse's labels on this one batch — they do not make Claude calibrated.

## Reproduce it

```bash
# 1. Judge a batch with Claude (isolated data dir, so the Jev radar is untouched)
paper-radar run -c radar.toml --backend claude --limit 50

# 2. Label the papers yourself — this is the step that makes it yours
paper-radar label <arxiv-id> yes   # or: no

# 3. Fit thresholds to your labels
paper-radar calibrate
```

Then compare your numbers with the first look above. If they disagree,
trust yours: your labels are the ground truth for your radar.
