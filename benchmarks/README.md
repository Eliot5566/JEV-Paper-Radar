# Benchmarks

Claims in the README that carry a number should be reproducible by someone who does not
trust them. This directory holds the code that produces those numbers.

## `clef_tar_2019/` — screening against real reviewers' decisions

Runs Paper Radar's screening mode over eight real Cochrane reviews and compares it with
what the reviewers themselves decided at the title-and-abstract stage.

```bash
python benchmarks/clef_tar_2019/run.py --backend mock --topics CD011571      # free, checks the wiring
python benchmarks/clef_tar_2019/run.py --criteria holdout --email you@...    # the headline numbers
python benchmarks/clef_tar_2019/run.py --criteria v1 --email you@...         # the development set
```

Three criteria sets, and the difference between them is most of what this benchmark
taught us:

- `criteria/v1/` — each review's published selection criteria translated literally.
- `criteria/v2/` — the same eight reviews after two rules were applied: one idea per
  criterion, and design criteria at the breadth the review actually screened at.
- `criteria/holdout/` — four reviews that were never looked at while anything was being
  diagnosed or changed. **These are the numbers to quote.**

Results land in `results.<set>.md` and are committed. `PREREGISTRATION.md` holds the
predictions made before each run, including the four of eight that were wrong.

### Why this dataset

The [CLEF eHealth Technology Assisted Reviews](https://github.com/CLEF-TAR/tar) track
published, for a set of Cochrane reviews, every record the review's Boolean search
returned along with the reviewers' relevance judgments. Two properties make it the right
choice here:

- **The judgments are abstract-level.** A dataset of final, post-full-text inclusions
  would flatter any screening tool, because a record that a human correctly passed at the
  abstract stage and only rejected after reading the full paper would be scored as a
  correct exclusion.
- **The topics are identifiable reviews.** Each topic is a Cochrane ID, so the review's
  own published selection criteria can be quoted rather than invented.

### Where the criteria come from

`criteria/*.toml` holds one file per topic. Each one quotes, verbatim, the SELECTION
CRITERIA section of that review's published abstract, then encodes it as Paper Radar
criteria directly beneath. The quote is there so the translation can be checked and
argued with — it is the step in this benchmark with the most room for an author to
flatter themselves, so it is the step most worth exposing.

Two reviews have a criterion that is a numeric comparison (a minimum trial duration, a
minimum follow-up). Paper Radar's design rule is that the model is never asked to compare
numbers or dates, so those are deliberately not encoded. It costs precision on those two
topics, and their criteria files say so.

### What the numbers do and do not show

The threshold is fitted per topic on the same judgments it is then measured against. That
is the optimistic case, and it is stated in the output. It answers "how well could this
separate the eligible studies from the rest, if you tuned it perfectly?" — not "what will
it do on your next review". For that second question, screen a few hundred records
yourself and run `paper-radar screen --report`.

Records that PubMed no longer serves are excluded from every figure and counted
separately. Records without an abstract are counted as kept, never as saved work; that is
the conservative choice and it pushes WSS down.

### Cost

About 8,400 judged records across the eight topics, of which roughly a third have no
abstract and are never sent to the model. Expect on the order of $0.20–$0.35 and a few
minutes, most of it waiting on NCBI's rate limit. Caches make reruns free.
