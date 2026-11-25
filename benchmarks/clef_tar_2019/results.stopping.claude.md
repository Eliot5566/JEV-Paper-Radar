# Stopping rules vs a fixed threshold — claude

Reviewer reads each review in order of eligibility. Recall target 95%. Development topics (8): settings chosen here. Test topics (4): reported.

| Rule | dev recall | dev WSS | dev topics < 95% | test recall (95% CI) | test WSS | test worst topic | test topics < 95% |
|---|--:|--:|--:|--:|--:|--:|--:|
| fixed threshold (fitted on other reviews) | 96.1% | 61.2% | 2 | 95.3% (90.1%–97.8%) | 58.3% | 81.8% | 1 |
| consecutive k=50 + floor | 97.5% | 59.0% | 0 | 95.3% (90.1%–97.8%) | 58.3% | 81.8% | 1 |
| consecutive k=100 + floor | 97.8% | 55.2% | 0 | 95.3% (90.1%–97.8%) | 57.9% | 81.8% | 1 |
| consecutive k=150 + floor | 98.2% | 51.9% | 0 | 95.3% (90.1%–97.8%) | 57.3% | 81.8% | 1 |
| consecutive k=200 + floor | 98.6% | 48.0% | 0 | 95.3% (90.1%–97.8%) | 56.6% | 81.8% | 1 |
| consecutive k=250 + floor | 99.3% | 43.4% | 0 | 96.1% (91.1%–98.3%) | 55.5% | 90.9% | 1 |
| consecutive k=300 + floor | 99.3% | 41.9% | 0 | 96.1% (91.1%–98.3%) | 54.7% | 90.9% | 1 |
| consecutive k=50 | 95.7% | 60.9% | 1 | 49.6% (41.1%–58.2%) | 39.1% | 30.7% | 3 |
| consecutive k=100 | 97.8% | 56.0% | 0 | 72.4% (64.1%–79.5%) | 57.1% | 62.5% | 2 |
| consecutive k=150 | 98.2% | 52.2% | 0 | 72.4% (64.1%–79.5%) | 56.1% | 62.5% | 2 |
| consecutive k=200 | 98.6% | 48.0% | 0 | 86.6% (79.6%–91.5%) | 64.2% | 81.8% | 2 |
| consecutive k=250 | 99.3% | 43.4% | 0 | 89.0% (82.3%–93.3%) | 63.2% | 85.2% | 2 |
| consecutive k=300 | 99.3% | 41.9% | 0 | 89.0% (82.3%–93.3%) | 62.1% | 85.2% | 2 |
| dry run max(50, 10% of read) | 95.7% | 60.8% | 1 | 49.6% (41.1%–58.2%) | 39.1% | 30.7% | 3 |
| dry run max(50, 20% of read) | 97.5% | 58.9% | 0 | 87.4% (80.5%–92.1%) | 64.6% | 81.8% | 3 |
| dry run max(50, 30% of read) | 98.6% | 50.8% | 0 | 96.9% (92.2%–98.8%) | 43.6% | 81.8% | 2 |
| dry run max(50, 50% of read) | 99.6% | 9.2% | 0 | 97.6% (93.3%–99.2%) | 32.1% | 81.8% | 2 |
| dry run max(100, 10% of read) | 97.8% | 56.0% | 0 | 72.4% (64.1%–79.5%) | 57.1% | 62.5% | 2 |
| dry run max(100, 20% of read) | 97.8% | 55.2% | 0 | 88.2% (81.4%–92.7%) | 64.3% | 81.8% | 2 |
| dry run max(100, 30% of read) | 98.6% | 48.2% | 0 | 97.6% (93.3%–99.2%) | 43.3% | 81.8% | 1 |
| dry run max(100, 50% of read) | 99.6% | 8.0% | 0 | 98.4% (94.4%–99.6%) | 31.8% | 81.8% | 1 |
| dry run max(30, 3% of review) | 90.3% | 59.7% | 4 | 87.4% (80.5%–92.1%) | 65.4% | 81.8% | 3 |
| dry run max(30, 5% of review) | 91.4% | 58.8% | 2 | 87.4% (80.5%–92.1%) | 63.6% | 81.8% | 3 |
| dry run max(30, 8% of review) | 97.5% | 55.0% | 1 | 96.1% (91.1%–98.3%) | 58.5% | 90.9% | 1 |
| dry run max(30, 12% of review) | 97.8% | 51.2% | 1 | 99.2% (95.7%–99.9%) | 45.7% | 98.9% | 0 |
| dry run max(50, 3% of review) **(chosen on dev)** | 97.5% | 60.0% | 0 | 87.4% (80.5%–92.1%) | 65.3% | 81.8% | 3 |
| dry run max(50, 5% of review) | 97.5% | 58.9% | 0 | 87.4% (80.5%–92.1%) | 63.6% | 81.8% | 3 |
| dry run max(50, 8% of review) | 98.2% | 54.3% | 0 | 96.1% (91.1%–98.3%) | 58.5% | 90.9% | 1 |
| dry run max(50, 12% of review) | 98.6% | 50.6% | 0 | 99.2% (95.7%–99.9%) | 45.7% | 98.9% | 0 |
| dry run max(100, 3% of review) | 97.8% | 55.6% | 0 | 88.2% (81.4%–92.7%) | 65.4% | 81.8% | 2 |
| dry run max(100, 5% of review) | 97.8% | 54.5% | 0 | 88.2% (81.4%–92.7%) | 63.8% | 81.8% | 2 |
| dry run max(100, 8% of review) | 98.6% | 50.1% | 0 | 96.1% (91.1%–98.3%) | 58.4% | 90.9% | 1 |
| dry run max(100, 12% of review) | 98.6% | 47.9% | 0 | 99.2% (95.7%–99.9%) | 45.7% | 98.9% | 0 |
| knee (adjusted, min 150 read) | 100.0% | 17.5% | 0 | 100.0% (97.1%–100.0%) | 22.9% | 100.0% | 0 |
| target t=10 (mean of 20 samples) | 93.2% | 45.6% | 4 | 95.3% (90.1%–97.8%) | 30.3% | 93.2% | 1 |

## Per test topic

| Rule | `CD008170` | `CD008201` | `CD012223` | `CD012347` |
|---|--:|--:|--:|--:|
| fixed threshold (fitted on other reviews) | 95% / 42% | 82% / 74% | 100% / 94% | 100% / 84% |
| dry run max(50, 3% of review) | 85% / 54% | 82% / 76% | 100% / 93% | 94% / 85% |
| knee (adjusted, min 150 read) | 100% / 0% | 100% / 68% | 100% / 74% | 100% / 17% |
| target t=10 (mean of 20 samples) | 93% / 36% | 100% / 14% | 100% / 26% | 100% / 36% |

Cells are recall / WSS. WSS counts every record read, including the target method's random sample and every record without an abstract (always read, never ranked).

Fixed threshold and floor: 0.405, fitted on the development reviews.

## Leave one review out: rule chosen on the other reviews

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | dry run max(50, 12% of review) | 98.2% | 54.7% | 96.4% | 66.9% |
| `CD006715` | dry run max(50, 12% of review) | 100.0% | 35.6% | 100.0% | 68.5% |
| `CD008018` | dry run max(50, 12% of review) | 100.0% | 70.6% | 100.0% | 58.3% |
| `CD008170` | dry run max(50, 12% of review) | 98.9% | 28.6% | 95.5% | 42.1% |
| `CD008201` | consecutive k=50 + floor | 81.8% | 74.2% | 81.8% | 74.2% |
| `CD010526` | dry run max(50, 12% of review) | 100.0% | 30.4% | 100.0% | 41.3% |
| `CD010778` | dry run max(50, 12% of review) | 100.0% | 46.0% | 100.0% | 55.5% |
| `CD011436` | dry run max(50, 12% of review) | 96.0% | 48.1% | 96.0% | 48.4% |
| `CD011571` | dry run max(30, 12% of review) | 86.7% | 41.5% | 86.7% | 62.0% |
| `CD012223` | dry run max(50, 12% of review) | 100.0% | 83.8% | 100.0% | 93.6% |
| `CD012347` | dry run max(50, 12% of review) | 100.0% | 77.5% | 100.0% | 83.6% |
| `CD012930` | dry run max(50, 12% of review) | 98.0% | 31.6% | 80.0% | 48.2% |

```
chosen rule      recall 97.8% (95% CI 95.8%–98.8%, 397/406) · pooled WSS 49.2% · reviews below 95%: 2
fixed threshold  recall 94.3% (95% CI 91.6%–96.2%, 383/406) · pooled WSS 58.2% · reviews below 95%: 3
```
