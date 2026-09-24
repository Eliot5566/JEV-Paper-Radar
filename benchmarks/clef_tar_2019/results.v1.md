# CLEF TAR 2019 — measured screening performance

Model: `jev-1.13.0` · recall target 95% · generated 2026-09-24

Abstract-level relevance judgments from the CLEF eHealth Technology Assisted Reviews
2019 track (Task 2, Intervention, training set). Criteria come from each review's own
published selection criteria; see `criteria/*.toml`, which quote the source verbatim.

| Topic | Review | Records | Eligible | Recall | Precision | WSS | Threshold | No abstract | Free hits | Cost |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `CD005139` | Anti-VEGF for neovascular age-related macular degene | 5,392 | 112 | 98.2% | 4.1% | 49.0% | 0.020 | 828 | 7 | $0.1478 |
| `CD006715` | Epidural analgesia for adults undergoing cardiac sur | 149 | 13 | 100.0% | 9.1% | 4.0% | 0.010 | 3 | 0 | $0.0052 |
| `CD008018` | Adjuvant GnRH analogues to prevent chemotherapy-indu | 739 | 17 | 100.0% | 12.9% | 82.1% | 0.090 | 48 | 0 | $0.0214 |
| `CD010526` | Dental cavity liners for Class I and Class II resin- | 652 | 21 | 95.2% | 9.1% | 61.5% | 0.040 | 19 | 0 | $0.0189 |
| `CD010778` | Intralesional treatment versus wide resection for ce | 339 | 26 | 96.2% | 36.2% | 75.8% | 0.150 | 20 | 0 | $0.0088 |
| `CD011436` | Ultrasound guidance for perioperative neuraxial and  | 290 | 25 | 100.0% | 9.8% | 11.7% | 0.010 | 16 | 0 | $0.0083 |
| `CD011571` | Antistreptococcal interventions for guttate and chro | 146 | 15 | 100.0% | 10.4% | 1.4% | 0.010 | 18 | 4 | $0.0041 |
| `CD012930` | Once-daily LABA/LAMA combination inhaler versus plac | 735 | 50 | 98.0% | 7.6% | 10.0% | 0.020 | 30 | 0 | $0.0250 |

**Pooled: 8,442 records, 279 eligible, recall 98.2%, WSS 47.7%, $0.24 total**

**Free hits: 11 of the 279 eligible studies (4%) had no abstract**, so they were kept by the no-abstract rule rather than found by the model. Recall would be 98.1% counting only the studies the model actually judged.

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
python benchmarks/clef_tar_2019/run.py --email you@example.com
```

Set `NCBI_API_KEY` to fetch faster. Everything is cached under `cache/`, so only the
first run pays for the download.
