# Which model, and when to stop reading: twelve CLEF TAR reviews

Measured 2026-11-25 on the same 27,889 records (12 Cochrane reviews, 406 eligible
studies) for Jev and Claude; Gemini finished only the eight development reviews. Each model judged every record once; everything below is
computed from those judgments by `loto.py`, `stopping.py` and `ensemble.py`, without
calling a model again.

## The honest comparison: nothing tuned on the review being scored

Leave one review out: the threshold, or the stopping rule, is chosen on the other
eleven reviews and applied to the twelfth.

| Model | How the reviewer stops | Recall (95% CI) | Work saved (WSS) | Reviews below 95% | Cost, 12 reviews |
|---|---|--:|--:|--:|--:|
| Jev `jev-1.13.0` | fixed threshold | 92.4% (89.4–94.6) | 46.3% | 3 | $0.84 |
| Jev `jev-1.13.0` | **ranked reading + stopping rule** | **98.0% (96.2–99.0)** | **69.1%** | **0** | $0.84 |
| Claude `claude-haiku-5-5` | fixed threshold | 94.3% (91.6–96.2) | 58.2% | 3 | $1.25 (Batch) |
| Claude `claude-haiku-5-5` | ranked reading + stopping rule | 97.8% (95.8–98.8) | 49.2% | 2 | $1.25 (Batch) |
| Jev + Claude, scores averaged | fixed threshold | 93.8% (91.1–95.8) | 55.0% | 3 | $2.09 |
| Jev + Claude, scores averaged | ranked reading + stopping rule | 98.5% (96.8–99.3) | 55.2% | 1 | $2.09 |

Jev read in ranked order with the stopping rule is the best combination on both axes:
more eligible studies found and more reading saved than any threshold, at the lowest
price. The rule it picks, in every fold, is "stop after max(100, 3% of the ranked
records) irrelevant records in a row" (the default of `paper-radar screen --progress`).

Claude ranks differently. Its scores sit on a steadier scale across reviews, so a fixed
threshold transfers better (58% saved against Jev's 46%), but its eligible studies are
spread deeper down the ranking, with long dry runs between them, so a dry-run rule
either stops too early or has to be so long that it saves less. Averaging the two
models' scores gives the steadiest threshold (99.2% recall and 56% saved on the four
held-out reviews), at twice the cost, and still saves less than Jev alone with the
stopping rule.

## Gemini Decision 1: development reviews only

Gemini judged the eight development reviews (8,441 records, nominal $0.48) but ran out
of time on the held-out ones. The development reviews took about 1½ hours on the free
tier; the held-out ones (19,447 records) were still running when the job hit its
340-minute limit 4 hours later. The log was buffered, so it does not say whether that
was the free tier's per-minute or daily limit. So the
three models can only be compared on the eight smaller reviews, leaving one out:

| Model | Fixed threshold: recall / WSS | Stopping rule: recall / WSS | Cost, 8 reviews |
|---|--:|--:|--:|
| Jev | 93.5% / 57.4% | 95.0% / 55.7% | $0.24 |
| Claude Haiku 5.5 | 93.9% / 59.7% | 95.7% / 59.5% | $0.35 (Batch) |
| Gemini Decision 1 | 93.9% / 58.5% | 97.1% / 56.8% | $0.48 (list price; ran on the free tier) |
| Jev + Claude | 93.9% / 59.7% | 98.2% / 51.2% | $0.59 |
| All three | 94.6% / 60.9% | 98.2% / 53.1% | $1.07 |

On these small reviews (146 to 5,392 records, 279 eligible studies in all) the three
models are within each other's confidence intervals (about ±3 points of recall). The
differences that matter show up on the large held-out reviews, which only Jev and
Claude finished. On the free tier, Gemini could not finish a full 19,000-record review
in four hours; a paid key, or `--topics` one review at a time, would be needed. [Full tables](results.stopping.dev-three-way.md);
[Gemini's own report](results.v2.gemini.md).

## The optimistic bound: threshold tuned on each review's own labels

| Model | Held-out 4 reviews: recall / WSS | Development 8 reviews: recall / WSS |
|---|--:|--:|
| Jev `jev-1.13.0` | 96.9% / 78.0% | 97.8% / 38.9% |
| Claude `claude-haiku-5-5` | 96.9% / 64.8% | 96.8% / 65.5% |
| Gemini `gemini-decision-1` | not finished | 96.4% / 65.8% |

Tuned per review, Jev separates the large held-out reviews better and Claude the small
development ones. Neither number is available to a team starting a new review; the
table above is.

## Caveats

- One run per model. Twelve reviews, of which three have fewer than 300 records; on
  those the dry run covers most of the pile and saves little, which is cheap anyway.
- The rule grid was widened once after the first look at Jev's results (the "% of the
  review" variants were added). Before that, the best fixed-length rule (200 in a row)
  gave Jev 99.0% recall and 63.8% saved under the same leave-one-review-out test.
- WSS counts every record a reviewer reads, including records without an abstract,
  which are always read and never ranked.

Full tables: [Jev](results.stopping.jev.md), [Claude](results.stopping.claude.md),
[Jev + Claude](results.stopping.jev+claude.md); Claude's own per-review reports:
[development](results.v2.claude.md), [held-out](results.holdout.claude.md).

## Reproducing

```bash
python benchmarks/clef_tar_2019/run.py --criteria v2 --model jev-1.13.0 --dump dumps/jev/v2
python benchmarks/clef_tar_2019/run.py --criteria holdout --model jev-1.13.0 --dump dumps/jev/holdout
python benchmarks/clef_tar_2019/run.py --backend claude --model claude-haiku-5-5 --batch --criteria v2 --dump dumps/claude/v2
python benchmarks/clef_tar_2019/run.py --backend claude --model claude-haiku-5-5 --batch --criteria holdout --dump dumps/claude/holdout
python benchmarks/clef_tar_2019/stopping.py dumps/jev/v2 dumps/jev/holdout --fit-on dumps/jev/v2 --label jev
python benchmarks/clef_tar_2019/ensemble.py dumps/jev/v2 dumps/claude/v2 --out dumps/jev+claude/v2   # and holdout
```
