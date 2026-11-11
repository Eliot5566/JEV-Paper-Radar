# Screening title/abstract records for a systematic review

A second screener for title-and-abstract screening, measured against what
Cochrane reviewers actually decided — not a replacement for one of your two
human screeners.

If you run systematic reviews, the problem this solves is concrete: a
Boolean search returns thousands of records, and two people have to read
every title and abstract. This mode reads them first and tells you which
ones it thinks are eligible, so a human reads the uncertain pile instead
of the whole pile. It never produces a final exclusion on its own, and its
exclusions are reported in the PRISMA 2020 box that exists for automation
tools, separately from human decisions.

## What it does

You write your review's eligibility criteria as statements — one PICO
element per criterion — and each record is judged against every one of
them. A record is eligible only if **every** include criterion holds, and
any one exclude criterion disqualifies it. That conjunction is the whole
difference from the daily paper radar, where interests combine with a max
and adding one can only help. Here every criterion you add is another
chance to veto a record, so keep the list short: the fewest criteria that
capture eligibility, each about something an abstract can actually answer.

Three deliberate choices, all visible in `paper_radar/screening.py`:

- **Every criterion counts.** The default combines the per-criterion
  probabilities with their geometric mean, not the weakest one. Using
  only the minimum throws away everything except one number — two
  records whose worst criterion scores 0.02 rank identically even when
  one matches the other criteria at 0.95 and the other at 0.10.
  `combine = "min"` restores the strict weakest-link reading.
- **No abstract means manual review, never exclusion.** About a third
  of new PubMed records have a title and nothing else (13 of 40 measured
  on consecutive records). Judging those on a title would produce
  confident nonsense, so they go to a manual pile and are never counted
  as saved work.
- **The threshold errs toward reading.** Missing an eligible study is
  the expensive error in a review; reading one extra abstract costs a
  minute. The threshold is fitted to a recall target you set
  (`target_recall`, default 0.95), not to accuracy.

Each run prints the PRISMA 2020 counts for the title/abstract stage:
records identified, records screened, records the tool marked ineligible
(split by exclusion criterion vs. below the eligibility threshold),
reports sought for retrieval, and records needing manual review. Every
screening record stores the model that produced it — a model change
mid-review is a protocol deviation, so pin `model` in your config.

## How to run it

```bash
cp profiles/systematic-review.toml review.toml
# Edit review.toml: your PubMed query, your include/exclude criteria.
paper-radar screen -c review.toml --limit 50   # a cheap first pass
paper-radar screen -c review.toml              # the real screen
```

Then measure it against your own decisions, on records you have already
screened yourself:

```bash
paper-radar screen -c review.toml --report   # fits the threshold to your target recall
```

`--report` prints recall and precision at the fitted threshold, workload
saved (WSS), and the eligible studies it would have missed — read those
before trusting the threshold, they are what it costs you. Label a few
hundred records first; with fewer than 10 eligible studies in your sample
any fitted threshold is rough, and the tool says so.

## Measured against real reviewers' decisions

The benchmark is in `benchmarks/clef_tar_2019/`. It replays the CLEF
eHealth Technology Assisted Reviews 2019 track (Task 2, Intervention):
for a set of Cochrane reviews, every record the review's Boolean search
returned, along with the reviewers' own relevance judgments at the
title-and-abstract stage — the stage this tool works at. Each review's
criteria come from its own published selection criteria, quoted verbatim
in `benchmarks/clef_tar_2019/criteria/`, so the translation can be
checked and argued with.

Twelve reviews in total. Four of them were never looked at while
anything was being built or fixed, and **those four are the numbers to
quote**:

| Held-out review | Records | Eligible | Recall | Work saved (WSS) | Cost |
|---|--:|--:|--:|--:|--:|
| Antihypertensives: RAS inhibitors vs other classes | 12,319 | 88 | 95.5% | 68.1% | $0.37 |
| Thromboprophylaxis implementation | 3,574 | 11 | 100% | 95.1% | $0.11 |
| Cyclodestructive procedures for glaucoma | 2,456 | 12 | 100% | 95.8% | $0.08 |
| Psychological therapies for depression in COPD | 1,098 | 16 | 100% | 92.5% | $0.03 |

**19,447 records, 127 eligible studies, 96.9% recall, 78.0% pooled
work saved (WSS), $0.60, model `jev-1.13.0`, generated 2026-09-24.**

WSS — work saved over sampling — is the metric this literature uses: the
share of records a reviewer would not have to read, minus what pure
sampling at that recall would give for free. So 78% means roughly four
fifths of the pile not read, at 96.9% of eligible studies still found.

The other eight reviews, used during development, did far worse: 8,442
records, 279 eligible, pooled WSS 47.7% on the first criteria set and
38.9% after the criteria were rewritten. Individual topics ranged from
0.1% to 82%. **Performance is dominated by the review, not by the
tool.** The held-out reviews are large and low in prevalence (0.3–1.5%
eligible), which is the regime a real search is in; the development set
included 146-record topics where 10% of records were eligible and there
was little to save. Treat 78% as what a large search looks like, not as
a number you can expect.

The criteria rewrite itself was pre-registered:
`benchmarks/clef_tar_2019/PREREGISTRATION.md` holds the predictions made
before the run, including the ones that were wrong. Nothing in the
benchmark was tuned by looking at which records it would move.

To reproduce it (needs a TypeSafe key and an email for NCBI; the
`--backend mock` run only checks the wiring):

```bash
python benchmarks/clef_tar_2019/run.py --backend mock --topics CD011571
python benchmarks/clef_tar_2019/run.py --criteria holdout --email you@example.com
```

## How to read these numbers

- **The thresholds are fitted on the same judgments they are scored
  against.** That is the optimistic case. It answers "how well could
  this separate the eligible studies from the rest, if you tuned it
  perfectly?" — not "what will it do on your next review". For that
  second question, screen a few hundred records yourself and run
  `paper-radar screen --report`.
- **Recall is achieved, not targeted.** The threshold is the lowest
  score among the studies needed to reach the target, and you cannot
  keep a fraction of a study — so on a topic with few eligible studies
  the target rounds up to 100% recall, which pushes WSS down. Read the
  recall column next to every WSS figure.
- **One free hit.** 1 of the 127 eligible studies in the held-out set
  had no abstract, so it was kept by the no-abstract rule rather than
  found by the model. Recall counting only the studies the model
  actually judged is 96.8%.
- **The benchmark replays decisions that were already made.** Nobody
  has run this alongside a live review yet. If you shadow a review in
  progress, those numbers would be worth a pull request more than
  anything here.

## Honest limits

- **A second screener, not a replacement.** Published evaluations of
  automated screening report a mean recall around 93% and a mean
  WSS@95 of about 55%, and they consistently conclude that these tools
  belong alongside human reviewers rather than in place of one. Use it
  as a second screener, or to prioritise the order a human screens in.
- **Jev numbers only.** Every figure above was measured with Jev
  (`jev-1.13.0`), which returns calibrated probabilities. The Claude
  backend returns self-reported, uncalibrated probabilities: run
  `paper-radar calibrate` on Claude-judged labels and re-fit your
  thresholds before trusting a Claude screen, and do not apply the
  96.9% / 78% figures to it.
- **Abstracts only.** The model judges what the abstract says, not the
  full paper. Records without an abstract are never auto-excluded.
- **Jev is new.** It launched in early access in September 2026, and
  its benchmark numbers are TypeSafe's own and have not been
  reproduced independently. Pin `model` and use `calibrate`.
- **Titles and abstracts (public data) are sent to your chosen
  provider.** Nothing else is.

## Further reading

- The benchmark code and results: `benchmarks/clef_tar_2019/`
  (including `PREREGISTRATION.md` and `results.holdout.md`)
- Worked screening profile: `profiles/systematic-review.toml`
- The screening section of the README, with the same numbers and
  their caveats
