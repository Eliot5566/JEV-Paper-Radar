# Per-criterion dumps

`paper-radar screen --dump` writes one row per record: the probability each eligibility
criterion got, which one was weakest, the verdict, and the reviewers' own label. These
are the files behind the diagnosis in `../PREREGISTRATION.md`, kept so the claims there
can be checked rather than taken on trust.

What each one showed:

| file | topic | what it established |
|---|---|---|
| `CD011571.csv` | Antistreptococcal interventions for psoriasis | Five of eleven eligible studies scored below 0.25 on "is this a randomised controlled trial?" — and NLM tags those five as Controlled Clinical Trial, Clinical Trial or Systematic Review. The criterion was wrong, not the model. |
| `CD010778.csv` | Chondrosarcoma treatment | The contrast case: its design criterion ("reports outcomes for a series of treated patients") scored 0.97–0.99 on every eligible study and never bound. |
| `CD012930.csv` | LABA/LAMA for COPD | Half the eligible studies scored 0.02–0.09 on a criterion that bundled four conditions into one sentence, while scoring ~0.95 on the other two. |
| `CD006715.csv` | Epidural analgesia in cardiac surgery | The same compound-criterion failure, on eight of thirteen eligible studies. |
| `CD011436.csv` | Ultrasound-guided nerve blocks in children | Twenty-one of twenty-five eligible studies score above 0.81; two outliers set the threshold anyway, which is what WSS@95 does at small positive counts. |

Regenerate any of them:

```bash
python benchmarks/clef_tar_2019/run.py --criteria v1 --topics CD011571 --dump diag --email you@example.com
```

These came from the `v1` (literal) criteria. The numbers moved substantially under `v2`;
that is the point of keeping both.
