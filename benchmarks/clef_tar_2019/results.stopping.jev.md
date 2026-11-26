# Stopping rules vs a fixed threshold — jev

Reviewer reads each review in order of eligibility. Recall target 95%. Development topics (8): settings chosen here. Test topics (4): reported.

| Rule | dev recall | dev WSS | dev topics < 95% | test recall (95% CI) | test WSS | test worst topic | test topics < 95% |
|---|--:|--:|--:|--:|--:|--:|--:|
| fixed threshold (fitted on other reviews) | 95.3% | 55.4% | 3 | 99.2% (95.7%–99.9%) | 43.2% | 98.9% | 0 |
| consecutive k=50 + floor | 97.5% | 54.3% | 2 | 99.2% (95.7%–99.9%) | 43.2% | 98.9% | 0 |
| consecutive k=100 + floor | 98.6% | 51.7% | 0 | 99.2% (95.7%–99.9%) | 43.0% | 98.9% | 0 |
| consecutive k=150 + floor | 98.9% | 48.8% | 0 | 99.2% (95.7%–99.9%) | 42.6% | 98.9% | 0 |
| consecutive k=200 + floor | 98.9% | 46.6% | 0 | 99.2% (95.7%–99.9%) | 42.1% | 98.9% | 0 |
| consecutive k=250 + floor | 98.9% | 44.8% | 0 | 99.2% (95.7%–99.9%) | 41.6% | 98.9% | 0 |
| consecutive k=300 + floor | 98.9% | 43.1% | 0 | 99.2% (95.7%–99.9%) | 41.1% | 98.9% | 0 |
| consecutive k=50 | 91.0% | 60.5% | 4 | 81.9% (74.3%–87.6%) | 68.1% | 73.9% | 1 |
| consecutive k=100 | 95.0% | 55.7% | 1 | 81.9% (74.3%–87.6%) | 67.1% | 73.9% | 1 |
| consecutive k=150 | 98.9% | 50.2% | 0 | 85.8% (78.7%–90.8%) | 68.4% | 79.5% | 1 |
| consecutive k=200 | 98.9% | 47.4% | 0 | 97.6% (93.3%–99.2%) | 74.1% | 96.6% | 0 |
| consecutive k=250 | 98.9% | 45.0% | 0 | 97.6% (93.3%–99.2%) | 73.1% | 96.6% | 0 |
| consecutive k=300 | 98.9% | 43.1% | 0 | 97.6% (93.3%–99.2%) | 72.0% | 96.6% | 0 |
| dry run max(50, 10% of read) | 91.0% | 60.5% | 4 | 81.9% (74.3%–87.6%) | 67.9% | 73.9% | 1 |
| dry run max(50, 20% of read) | 97.8% | 56.0% | 2 | 99.2% (95.7%–99.9%) | 73.4% | 98.9% | 0 |
| dry run max(50, 30% of read) | 98.6% | 44.2% | 2 | 99.2% (95.7%–99.9%) | 71.0% | 98.9% | 0 |
| dry run max(50, 50% of read) | 98.9% | 15.2% | 2 | 99.2% (95.7%–99.9%) | 63.1% | 98.9% | 0 |
| dry run max(100, 10% of read) | 95.0% | 55.7% | 1 | 81.9% (74.3%–87.6%) | 67.1% | 73.9% | 1 |
| dry run max(100, 20% of read) | 98.6% | 52.3% | 0 | 99.2% (95.7%–99.9%) | 72.6% | 98.9% | 0 |
| dry run max(100, 30% of read) | 99.3% | 40.9% | 0 | 99.2% (95.7%–99.9%) | 70.2% | 98.9% | 0 |
| dry run max(100, 50% of read) | 99.6% | 12.3% | 0 | 99.2% (95.7%–99.9%) | 62.6% | 98.9% | 0 |
| dry run max(30, 3% of review) | 91.4% | 59.2% | 4 | 96.1% (91.1%–98.3%) | 74.1% | 87.5% | 1 |
| dry run max(30, 5% of review) | 91.4% | 58.0% | 4 | 99.2% (95.7%–99.9%) | 72.9% | 98.9% | 0 |
| dry run max(30, 8% of review) | 97.5% | 51.2% | 3 | 99.2% (95.7%–99.9%) | 70.1% | 98.9% | 0 |
| dry run max(30, 12% of review) | 98.6% | 47.7% | 1 | 99.2% (95.7%–99.9%) | 66.4% | 98.9% | 0 |
| dry run max(50, 3% of review) | 96.8% | 59.0% | 3 | 97.6% (93.3%–99.2%) | 75.3% | 96.6% | 0 |
| dry run max(50, 5% of review) | 96.8% | 57.9% | 3 | 99.2% (95.7%–99.9%) | 72.9% | 98.9% | 0 |
| dry run max(50, 8% of review) | 97.5% | 50.3% | 3 | 99.2% (95.7%–99.9%) | 70.1% | 98.9% | 0 |
| dry run max(50, 12% of review) | 98.6% | 46.9% | 1 | 99.2% (95.7%–99.9%) | 66.4% | 98.9% | 0 |
| dry run max(100, 3% of review) **(chosen on dev)** | 98.2% | 54.8% | 0 | 97.6% (93.3%–99.2%) | 74.9% | 96.6% | 0 |
| dry run max(100, 5% of review) | 98.2% | 53.7% | 0 | 99.2% (95.7%–99.9%) | 72.6% | 98.9% | 0 |
| dry run max(100, 8% of review) | 98.9% | 46.2% | 0 | 99.2% (95.7%–99.9%) | 70.0% | 98.9% | 0 |
| dry run max(100, 12% of review) | 98.9% | 44.1% | 0 | 99.2% (95.7%–99.9%) | 66.4% | 98.9% | 0 |
| knee (adjusted, min 150 read) | 100.0% | 4.6% | 0 | 99.2% (95.7%–99.9%) | 28.1% | 98.9% | 0 |
| target t=10 (mean of 20 samples) | 93.9% | 44.7% | 4 | 93.7% (88.1%–96.8%) | 41.6% | 90.9% | 1 |

## Per test topic

| Rule | `CD008170` | `CD008201` | `CD012223` | `CD012347` |
|---|--:|--:|--:|--:|
| fixed threshold (fitted on other reviews) | 99% / 19% | 100% / 81% | 100% / 93% | 100% / 81% |
| dry run max(100, 3% of review) | 97% / 66% | 100% / 92% | 100% / 92% | 100% / 84% |
| knee (adjusted, min 150 read) | 99% / 7% | 100% / 63% | 100% / 81% | 100% / 32% |
| target t=10 (mean of 20 samples) | 91% / 53% | 100% / 17% | 100% / 24% | 100% / 37% |

Cells are recall / WSS. WSS counts every record read, including the target method's random sample and every record without an abstract (always read, never ranked).

Fixed threshold and floor: 0.230, fitted on the development reviews.

## Leave one review out: rule chosen on the other reviews

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | dry run max(100, 3% of review) | 97.3% | 61.2% | 79.5% | 57.1% |
| `CD006715` | dry run max(100, 3% of review) | 100.0% | 0.7% | 100.0% | 65.8% |
| `CD008018` | dry run max(100, 3% of review) | 100.0% | 67.0% | 100.0% | 52.2% |
| `CD008170` | dry run max(100, 3% of review) | 96.6% | 66.1% | 98.9% | 22.5% |
| `CD008201` | dry run max(100, 3% of review) | 100.0% | 92.2% | 100.0% | 85.8% |
| `CD010526` | dry run max(100, 3% of review) | 100.0% | 54.6% | 100.0% | 56.4% |
| `CD010778` | dry run max(100, 3% of review) | 100.0% | 46.9% | 100.0% | 59.6% |
| `CD011436` | dry run max(100, 3% of review) | 96.0% | 41.2% | 100.0% | 35.5% |
| `CD011571` | dry run max(100, 3% of review) | 100.0% | 0.0% | 80.0% | 58.1% |
| `CD012223` | dry run max(100, 3% of review) | 100.0% | 91.9% | 100.0% | 95.1% |
| `CD012347` | dry run max(100, 3% of review) | 100.0% | 83.6% | 100.0% | 83.8% |
| `CD012930` | dry run max(100, 3% of review) | 98.0% | 23.9% | 92.0% | 39.8% |

```
chosen rule      recall 98.0% (95% CI 96.2%–99.0%, 398/406) · pooled WSS 69.1% · reviews below 95%: 0
fixed threshold  recall 92.4% (95% CI 89.4%–94.6%, 375/406) · pooled WSS 46.3% · reviews below 95%: 3
```
