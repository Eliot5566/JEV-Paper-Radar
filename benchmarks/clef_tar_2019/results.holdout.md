# CLEF TAR 2019 — measured screening performance

Model: `jev-1.13.0` · criteria `holdout` · recall target 95% · generated 2026-09-24

Abstract-level relevance judgments from the CLEF eHealth Technology Assisted Reviews
2019 track (Task 2, Intervention, training set). Criteria come from each review's own
published selection criteria; see `criteria/*.toml`, which quote the source verbatim.

Both aggregation rules are scored from the same Jev answers, so the comparison is
paired: no record is judged twice and no run-to-run variation enters it.

| Topic | Review | Records | Eligible | geometric recall | geometric WSS | min recall | min WSS | No abstract | Cost |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `CD008170` | First-line renin angiotensin system inhibitors | 12,319 | 88 | 95.5% | **68.1%** | 95.5% | 66.9% | 1271 | $0.3699 |
| `CD008201` | Interventions for implementation of thrombopro | 3,574 | 11 | 100.0% | **95.1%** | 100.0% | 96.3% | 87 | $0.1144 |
| `CD012223` | Cyclodestructive procedures for refractory gla | 2,456 | 12 | 100.0% | **95.8%** | 100.0% | 95.2% | 68 | $0.0779 |
| `CD012347` | Psychological therapies for depression in chro | 1,098 | 16 | 100.0% | **92.5%** | 100.0% | 88.9% | 5 | $0.0346 |

```
records    19,447   eligible 127   cost $0.60
geometric  recall  96.9% · pooled WSS  78.0% · median WSS  93.8%
min        recall  96.9% · pooled WSS  77.1% · median WSS  92.0%
```

**Free hits: 1 of the 127 eligible studies (1%) had no abstract**, so they were kept by the no-abstract rule rather than found by the model. Recall would be 96.8% counting only the studies the model actually judged.

1 judged records could not be retrieved from PubMed and are excluded from every figure above; 0 request(s) failed.

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
python benchmarks/clef_tar_2019/run.py --criteria holdout --email you@example.com
```

Set `NCBI_API_KEY` to fetch faster. Everything is cached under `cache/`, so only the
first run pays for the download.
