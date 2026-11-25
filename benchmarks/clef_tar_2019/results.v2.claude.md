# CLEF TAR 2019 — measured screening performance

Model: `claude-haiku-5-5` · criteria `v2` · recall target 95% · generated 2026-11-25

Abstract-level relevance judgments from the CLEF eHealth Technology Assisted Reviews
2019 track (Task 2, Intervention, training set). Criteria come from each review's own
published selection criteria; see `criteria/*.toml`, which quote the source verbatim.

Both aggregation rules are scored from the same model answers, so the comparison is
paired: no record is judged twice and no run-to-run variation enters it.

| Topic | Review | Records | Eligible | geometric recall | geometric WSS | min recall | min WSS | No abstract | Cost |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `CD005139` | Anti-VEGF for neovascular age-related macular  | 5,392 | 112 | 96.4% | **68.5%** | 99.1% | 33.5% | 828 | $0.2156 |
| `CD006715` | Epidural analgesia for adults undergoing cardi | 149 | 13 | 100.0% | **69.1%** | 100.0% | 43.0% | 3 | $0.0080 |
| `CD008018` | Adjuvant GnRH analogues to prevent chemotherap | 739 | 17 | 100.0% | **81.7%** | 100.0% | 81.1% | 48 | $0.0327 |
| `CD010526` | Dental cavity liners for Class I and Class II  | 652 | 21 | 95.2% | **42.2%** | 95.2% | 27.6% | 19 | $0.0277 |
| `CD010778` | Intralesional treatment versus wide resection  | 339 | 26 | 96.2% | **64.3%** | 96.2% | 58.7% | 20 | $0.0117 |
| `CD011436` | Ultrasound guidance for perioperative neuraxia | 290 | 25 | 96.0% | **65.0%** | 100.0% | 54.5% | 16 | $0.0126 |
| `CD011571` | Antistreptococcal interventions for guttate an | 146 | 15 | 100.0% | **47.3%** | 100.0% | 41.8% | 18 | $0.0057 |
| `CD012930` | Once-daily LABA/LAMA combination inhaler versu | 735 | 50 | 96.0% | **51.5%** | 98.0% | 2.6% | 30 | $0.0367 |

```
records    8,442   eligible 279   cost $0.35
geometric  recall  96.8% · pooled WSS  65.5% · median WSS  64.6%
min        recall  98.6% · pooled WSS  36.6% · median WSS  42.4%
```

**Free hits: 11 of the 279 eligible studies (4%) had no abstract**, so they were kept by the no-abstract rule rather than found by the model. Recall would be 96.6% counting only the studies the model actually judged.

5 judged records could not be retrieved from PubMed and are excluded from every figure above; 0 request(s) failed.

## How to read this

`WSS` is work saved over sampling at the recall actually achieved: the share of records a
reviewer would not have to read, minus what pure sampling at that recall would give for
free. It is the metric this literature uses, so these numbers are comparable to published
tools. Three things keep them from being better than they look:

1. **The threshold is fitted per topic on the same judgments it is measured against.**
   That is the optimistic case. It answers "how well could this separate eligible studies
   from the rest if you tuned it perfectly?", not "what will it do on your next review".
2. **Recall is achieved, not targeted.** The threshold is the lowest score among the
   studies needed to reach the target, and you cannot keep a fraction of a study — so on
   a topic with few eligible studies the target rounds up to 100% recall, which pushes WSS
   down. Read the Recall column next to every WSS figure.
3. **Free hits.** Records without an abstract are always kept, never counted as saved work.
   When one of them is an eligible study, the model did not find it; a rule did. The
   "Free hits" column counts those, and the line under the table restates recall without
   them.

## Reproducing

```bash
python benchmarks/clef_tar_2019/run.py --backend claude --model claude-haiku-5-5 --batch --criteria v2 --email you@example.com
```

Set `NCBI_API_KEY` to fetch faster. Everything is cached under `cache/`, so only the
first run pays for the download.
