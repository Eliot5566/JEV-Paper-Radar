# Pre-registration for the v2 criteria run

Written and committed **before** the v2 run, so that the diagnosis can be wrong in
public. v1's numbers are in `results.v1.md` and are not edited.

## What changed, and why it does not depend on the outcome

The v1 criteria were a literal translation of each review's published selection
criteria. Two of the ways they were written are defensible only until you look at them:

**R1 — one idea per criterion.** This project's README tells its own users to split a
criterion that bundles several conditions. Several v1 criteria broke that rule; the worst
was CD012930's intervention criterion, which bundled four conditions into one sentence
(once-daily, fixed-dose, LABA+LAMA in one inhaler, versus placebo). Splitting them is
applying the project's documented rule to itself, not tuning.

**R2 — design criteria at the breadth the review actually screened at.** Abstract-stage
screening errs toward inclusion on study design, because abstracts frequently do not
state it. v1 encoded "randomised controlled trial" as a hard conjunctive requirement.
That is measurably not the bar the reviewers applied: NLM tags only 47% of CD011571's
abstract-stage inclusions as "Randomized Controlled Trial", and across all eight topics
the figure ranges from 0% to 94%.

Both rules were applied to every topic, including the four that already scored well.
No criterion was written by looking at which records it would move.

## What went wrong in v1, per topic

Three distinct mechanisms, from the per-criterion dumps:

1. **Criterion stricter than the gold standard** — CD011571. Five of its eleven judged
   eligible studies scored below 0.25 on "is an RCT". Checked against NLM's own
   PublicationType on eight records, Jev agreed 8/8: those studies really are tagged
   "Controlled Clinical Trial", "Clinical Trial", or in one case "Systematic Review".
   The model was right and the criterion was wrong.
2. **Compound criterion** — CD012930, CD006715. Half of CD012930's eligible studies
   scored 0.01–0.09 on the bundled intervention criterion while scoring ~0.95 on the
   other two.
3. **Threshold pinned by one or two outliers** — CD011436. Twenty-one of its
   twenty-five eligible studies score above 0.81, but `ceil(25 × 0.95) = 24` allows
   dropping only one, so the second-worst record at 0.02 sets the threshold. Nothing
   about the criteria causes this; it is a property of WSS@95 at small positive counts.

## Predictions

Stated before running. Mechanism 3 is not addressed by either rule, so the topics whose
problem is mechanism 3 should barely move — that is the part of this that can fail.

| Topic | v1 WSS | Mechanism | Prediction for v2 |
|---|--:|---|---|
| `CD011571` | 1.4% | 1 | large rise, above 40% |
| `CD012930` | 10.0% | 2 | large rise, above 40% |
| `CD006715` | 4.0% | 2 and 3 | rise, but less than CD012930 |
| `CD011436` | 11.7% | 3 | little change, stays below 30% |
| `CD005139` | 49.0% | — | roughly unchanged, ±15 points |
| `CD010526` | 61.5% | — | roughly unchanged, ±15 points |
| `CD010778` | 76.1% | — | roughly unchanged, ±15 points |
| `CD008018` | 82.1% | — | roughly unchanged, ±15 points |

Pooled: v1 was 47.7%. Predicted v2 pooled WSS is higher but **below 70%**.

Recall is expected to stay at or above the v1 level everywhere, since every change
widens a criterion rather than narrowing it.

## What would falsify the diagnosis

- CD011571 or CD012930 failing to improve materially would mean the binding constraint
  was not the criterion wording.
- CD011436 improving a lot would mean mechanism 3 was misdiagnosed and the outlier
  records were a criteria problem after all.
- Any topic's recall dropping would mean a "widened" criterion was not actually wider.

Whatever happens, both tables stay in `results.v1.md` and `results.v2.md`.

---

# Round 2: the aggregation rule, on held-out topics

Written before the held-out run. Round 1's predictions were scored openly above and
four of eight were wrong, including the pooled direction. This round exists because
round 1's failure had a clear cause.

## What round 1 got wrong, and what it taught

v2 split compound criteria into separate ones, expecting that to help. On CD012930 it
took WSS from 10.0% to **0.1%**, and on CD005139 from 49.0% to 31.6%. The reason is
arithmetic and I should have seen it: eligibility was `min(p)` over the criteria, and
`min` over more terms can only go down. Splitting a criterion under a conjunction does
not relax it — it adds another veto.

The deeper problem is that `min` discards every number except one. Two records whose
worst criterion is 0.02 score identically even when one matches everything else at 0.95
and the other at 0.10. That is most of the signal, thrown away.

## The change

`screening.combine` now defaults to `"geometric"` — the geometric mean of the include
criteria — with `"min"` kept as an option. The geometric mean is the product (the
conjunction under independence) rescaled so a threshold means the same thing whether a
review has three criteria or six. Within one review the rescaling does not alter the
ranking, so in effect: use every criterion's evidence rather than only the weakest.
It is still a conjunction — one criterion near zero still sinks the record.

## Why this run is on different topics

The eight topics above have now been looked at twice. Fitting a third change to them
would not be a test. The CLEF TAR 2019 Intervention training set has twenty topics; four
of the twelve untouched ones have at least ten eligible studies, which is the point below
which `ceil(0.95n) = n` forces 100% recall and WSS is decided by a single record:

`CD012347` (1,098 records, 16 eligible) · `CD012223` (2,456 / 12) ·
`CD008201` (3,574 / 11) · `CD008170` (12,320 / 88)

Their criteria were written once, from each review's published selection criteria, using
the same two rules as v2, and were not revised after any result. Both aggregation rules
are scored from the same Jev answers, so the comparison is paired.

## Predictions

1. **Geometric beats min on pooled WSS** on these four topics. This is the main claim.
2. **The gap is largest where criteria are most numerous** — `CD012347` and `CD008170`
   have four include criteria, `CD012223` and `CD008201` have three.
3. **Recall is not worse under geometric** than under min, on any topic.
4. Absolute pooled WSS under geometric lands **between 30% and 70%**.

## What would falsify it

- Geometric losing to min on pooled WSS, or on three of the four topics.
- Geometric winning only on the three-criterion topics, which would mean the criterion
  count is not what drives the difference.
- Any topic where geometric's recall is materially below min's.

If the result is that `min` was fine and the criteria were the whole story, that goes in
the README as written, and the default goes back.

## Round 2 result, scored

| Prediction | Outcome |
|---|---|
| 1. Geometric beats min on pooled WSS | **correct**, 78.0% vs 77.1% — a 0.9 point margin |
| 2. Gap largest where criteria are most numerous | **directionally correct**: the two four-criterion topics gained most (+3.6, +1.2), the three-criterion ones +0.6 and −1.2. Four topics cannot establish this. |
| 3. Recall not worse under geometric | **correct**, identical on every topic |
| 4. Pooled WSS between 30% and 70% | **wrong**, it was 78.0% |

Three of four, and the miss was in the generous direction.

The claim the change was built on survives, but the effect is about one point and one
topic went the other way. The default stays `geometric` because it is principled, costs
nothing and never reduced recall — not because it rescued anything.

## The finding neither round predicted

The held-out topics score far better than the eight the tool was developed on, and the
paired `min` column shows it is not the aggregation rule doing it:

| set | topics | pooled WSS | median WSS | records per topic | eligible rate |
|---|--:|--:|--:|---|---|
| development (v1 criteria) | 8 | 47.7% | 30.4% | 146–5,392 | 2%–10% |
| development (v2 criteria) | 8 | 38.9% | 63.1% | 146–5,392 | 2%–10% |
| held-out (geometric) | 4 | **78.0%** | **93.8%** | 1,098–12,319 | 0.3%–1.5% |
| held-out (min) | 4 | 77.1% | 92.0% | 1,098–12,319 | 0.3%–1.5% |

Performance is dominated by the topic, not by anything changed across three rounds. The
held-out reviews are larger and much lower in prevalence, which is the regime a real
systematic review search is actually in — thousands of records, well under 1% eligible.

This is not a clean causal claim. The held-out set differs in size, in prevalence and in
which round wrote its criteria, and four topics cannot separate those. What it does
establish is that a single headline WSS for this tool would be meaningless: the spread
across reviews is far wider than the spread across anything implemented here.
