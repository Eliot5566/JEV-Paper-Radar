# Development reviews only: Jev vs Claude vs Gemini

Gemini Decision 1 finished the eight development reviews but not the held-out ones (the free-tier rate limit; the job hit the 340-minute limit inside the 12,319-record review). This compares all three, and their averages, on the eight reviews every model judged, leaving one review out.


## Jev `jev-1.13.0`

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | consecutive k=100 | 89.3% | 59.7% | 87.5% | 62.0% |
| `CD006715` | dry run max(100, 3% of review) | 100.0% | 0.7% | 100.0% | 59.7% |
| `CD008018` | dry run max(100, 3% of review) | 100.0% | 67.0% | 100.0% | 44.5% |
| `CD010526` | dry run max(100, 3% of review) | 100.0% | 54.6% | 100.0% | 47.9% |
| `CD010778` | dry run max(100, 3% of review) | 100.0% | 46.9% | 100.0% | 43.7% |
| `CD011436` | dry run max(100, 3% of review) | 96.0% | 41.2% | 100.0% | 29.7% |
| `CD011571` | dry run max(100, 3% of review) | 100.0% | 0.0% | 93.3% | 68.0% |
| `CD012930` | dry run max(100, 3% of review) | 98.0% | 23.9% | 94.0% | 35.1% |

```
chosen rule      recall 95.0% (95% CI 91.8%–97.0%, 265/279) · pooled WSS 55.7% · reviews below 95%: 1
fixed threshold  recall 93.5% (95% CI 90.0%–95.9%, 261/279) · pooled WSS 57.4% · reviews below 95%: 3
```


## Claude `claude-haiku-5-5`

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | consecutive k=50 | 92.0% | 66.0% | 96.4% | 66.9% |
| `CD006715` | dry run max(50, 3% of review) | 100.0% | 35.6% | 100.0% | 68.5% |
| `CD008018` | consecutive k=50 + floor | 100.0% | 58.3% | 100.0% | 58.3% |
| `CD010526` | dry run max(50, 3% of review) | 100.0% | 34.2% | 100.0% | 41.3% |
| `CD010778` | dry run max(50, 3% of review) | 100.0% | 46.0% | 100.0% | 55.5% |
| `CD011436` | dry run max(50, 3% of review) | 96.0% | 48.1% | 96.0% | 48.4% |
| `CD011571` | dry run max(50, 3% of review) | 100.0% | 13.0% | 86.7% | 62.0% |
| `CD012930` | dry run max(50, 3% of review) | 96.0% | 45.1% | 80.0% | 48.2% |

```
chosen rule      recall 95.7% (95% CI 92.6%–97.5%, 267/279) · pooled WSS 59.5% · reviews below 95%: 1
fixed threshold  recall 93.9% (95% CI 90.5%–96.2%, 262/279) · pooled WSS 59.7% · reviews below 95%: 2
```


## Gemini `gemini-decision-1`

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | consecutive k=100 | 95.5% | 64.1% | 95.5% | 64.6% |
| `CD006715` | consecutive k=100 | 100.0% | 1.3% | 100.0% | 67.8% |
| `CD008018` | consecutive k=100 | 100.0% | 71.3% | 100.0% | 66.6% |
| `CD010526` | consecutive k=100 | 95.2% | 44.6% | 100.0% | 44.6% |
| `CD010778` | consecutive k=100 | 100.0% | 36.3% | 100.0% | 45.7% |
| `CD011436` | consecutive k=100 | 100.0% | 8.6% | 96.0% | 41.2% |
| `CD011571` | consecutive k=50 + floor | 93.3% | 35.8% | 80.0% | 58.1% |
| `CD012930` | consecutive k=100 | 98.0% | 36.1% | 84.0% | 44.7% |

```
chosen rule      recall 97.1% (95% CI 94.4%–98.5%, 271/279) · pooled WSS 56.8% · reviews below 95%: 1
fixed threshold  recall 93.9% (95% CI 90.5%–96.2%, 262/279) · pooled WSS 58.5% · reviews below 95%: 2
```


## Jev + Claude, averaged

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | dry run max(30, 12% of review) | 98.2% | 54.9% | 92.0% | 64.7% |
| `CD006715` | consecutive k=50 + floor | 100.0% | 38.9% | 100.0% | 69.1% |
| `CD008018` | consecutive k=50 + floor | 100.0% | 55.8% | 100.0% | 55.8% |
| `CD010526` | consecutive k=50 + floor | 100.0% | 46.3% | 100.0% | 46.3% |
| `CD010778` | consecutive k=50 + floor | 100.0% | 55.8% | 100.0% | 55.8% |
| `CD011436` | consecutive k=50 + floor | 96.0% | 41.2% | 96.0% | 41.2% |
| `CD011571` | consecutive k=50 + floor | 100.0% | 15.1% | 80.0% | 58.1% |
| `CD012930` | consecutive k=50 + floor | 96.0% | 37.9% | 92.0% | 43.7% |

```
chosen rule      recall 98.2% (95% CI 95.9%–99.2%, 274/279) · pooled WSS 51.2% · reviews below 95%: 0
fixed threshold  recall 93.9% (95% CI 90.5%–96.2%, 262/279) · pooled WSS 59.7% · reviews below 95%: 3
```


## Jev + Gemini, averaged

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | consecutive k=100 | 92.0% | 63.9% | 92.0% | 65.2% |
| `CD006715` | dry run max(100, 3% of review) | 100.0% | 0.7% | 100.0% | 67.8% |
| `CD008018` | dry run max(100, 3% of review) | 100.0% | 69.7% | 100.0% | 57.0% |
| `CD010526` | dry run max(100, 3% of review) | 100.0% | 47.1% | 100.0% | 46.8% |
| `CD010778` | dry run max(100, 3% of review) | 100.0% | 41.9% | 100.0% | 46.9% |
| `CD011436` | dry run max(100, 3% of review) | 96.0% | 41.2% | 100.0% | 36.2% |
| `CD011571` | dry run max(50, 3% of review) | 93.3% | 35.8% | 80.0% | 58.1% |
| `CD012930` | dry run max(100, 3% of review) | 98.0% | 29.6% | 94.0% | 46.1% |

```
chosen rule      recall 95.7% (95% CI 92.6%–97.5%, 267/279) · pooled WSS 58.1% · reviews below 95%: 2
fixed threshold  recall 94.6% (95% CI 91.3%–96.7%, 264/279) · pooled WSS 60.2% · reviews below 95%: 3
```


## All three, averaged

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | dry run max(50, 8% of review) | 98.2% | 58.1% | 94.6% | 67.2% |
| `CD006715` | consecutive k=100 + floor | 100.0% | 4.0% | 100.0% | 68.5% |
| `CD008018` | dry run max(50, 3% of review) | 94.1% | 77.6% | 100.0% | 59.8% |
| `CD010526` | consecutive k=100 + floor | 100.0% | 42.6% | 100.0% | 44.2% |
| `CD010778` | consecutive k=100 + floor | 100.0% | 47.5% | 100.0% | 54.3% |
| `CD011436` | consecutive k=100 + floor | 96.0% | 36.7% | 96.0% | 43.9% |
| `CD011571` | consecutive k=100 + floor | 100.0% | 0.0% | 80.0% | 57.4% |
| `CD012930` | consecutive k=100 + floor | 98.0% | 28.9% | 90.0% | 46.5% |

```
chosen rule      recall 98.2% (95% CI 95.9%–99.2%, 274/279) · pooled WSS 53.1% · reviews below 95%: 1
fixed threshold  recall 94.6% (95% CI 91.3%–96.7%, 264/279) · pooled WSS 60.9% · reviews below 95%: 3
```

