# Stopping rules vs a fixed threshold — jev+claude

Reviewer reads each review in order of eligibility. Recall target 95%. Development topics (8): settings chosen here. Test topics (4): reported.

| Rule | dev recall | dev WSS | dev topics < 95% | test recall (95% CI) | test WSS | test worst topic | test topics < 95% |
|---|--:|--:|--:|--:|--:|--:|--:|
| fixed threshold (fitted on other reviews) | 95.3% | 60.4% | 3 | 99.2% (95.7%–99.9%) | 56.0% | 98.9% | 0 |
| consecutive k=50 + floor **(chosen on dev)** | 97.8% | 59.0% | 0 | 99.2% (95.7%–99.9%) | 55.8% | 98.9% | 0 |
| consecutive k=100 + floor | 98.2% | 55.9% | 0 | 99.2% (95.7%–99.9%) | 55.2% | 98.9% | 0 |
| consecutive k=150 + floor | 98.9% | 51.1% | 0 | 99.2% (95.7%–99.9%) | 54.4% | 98.9% | 0 |
| consecutive k=200 + floor | 99.3% | 47.3% | 0 | 99.2% (95.7%–99.9%) | 53.6% | 98.9% | 0 |
| consecutive k=250 + floor | 99.3% | 44.9% | 0 | 99.2% (95.7%–99.9%) | 52.9% | 98.9% | 0 |
| consecutive k=300 + floor | 99.3% | 43.1% | 0 | 99.2% (95.7%–99.9%) | 52.1% | 98.9% | 0 |
| consecutive k=50 | 88.9% | 60.6% | 4 | 73.2% (64.9%–80.2%) | 60.5% | 63.6% | 2 |
| consecutive k=100 | 98.2% | 57.0% | 0 | 74.0% (65.8%–80.9%) | 60.0% | 63.6% | 2 |
| consecutive k=150 | 98.9% | 51.6% | 0 | 74.8% (66.6%–81.5%) | 59.1% | 63.6% | 1 |
| consecutive k=200 | 99.3% | 47.3% | 0 | 92.9% (87.1%–96.2%) | 68.9% | 89.8% | 1 |
| consecutive k=250 | 99.3% | 44.9% | 0 | 92.9% (87.1%–96.2%) | 67.8% | 89.8% | 1 |
| consecutive k=300 | 99.3% | 43.1% | 0 | 97.6% (93.3%–99.2%) | 67.5% | 96.6% | 0 |
| dry run max(50, 10% of read) | 88.9% | 60.6% | 4 | 73.2% (64.9%–80.2%) | 60.4% | 63.6% | 2 |
| dry run max(50, 20% of read) | 93.5% | 56.9% | 3 | 73.2% (64.9%–80.2%) | 59.9% | 63.6% | 2 |
| dry run max(50, 30% of read) | 97.1% | 52.9% | 2 | 97.6% (93.3%–99.2%) | 64.2% | 81.8% | 1 |
| dry run max(50, 50% of read) | 99.3% | 13.4% | 1 | 97.6% (93.3%–99.2%) | 54.1% | 81.8% | 1 |
| dry run max(100, 10% of read) | 98.2% | 57.0% | 0 | 74.0% (65.8%–80.9%) | 60.0% | 63.6% | 2 |
| dry run max(100, 20% of read) | 98.6% | 53.6% | 0 | 74.0% (65.8%–80.9%) | 59.6% | 63.6% | 2 |
| dry run max(100, 30% of read) | 98.9% | 49.4% | 0 | 98.4% (94.4%–99.6%) | 63.9% | 90.9% | 1 |
| dry run max(100, 50% of read) | 99.6% | 10.8% | 0 | 98.4% (94.4%–99.6%) | 54.0% | 90.9% | 1 |
| dry run max(30, 3% of review) | 93.2% | 61.6% | 3 | 97.6% (93.3%–99.2%) | 69.5% | 90.9% | 2 |
| dry run max(30, 5% of review) | 93.5% | 58.5% | 3 | 99.2% (95.7%–99.9%) | 68.3% | 98.9% | 0 |
| dry run max(30, 8% of review) | 93.5% | 56.2% | 3 | 99.2% (95.7%–99.9%) | 65.5% | 98.9% | 0 |
| dry run max(30, 12% of review) | 98.6% | 53.5% | 0 | 99.2% (95.7%–99.9%) | 61.8% | 98.9% | 0 |
| dry run max(50, 3% of review) | 93.2% | 59.9% | 3 | 98.4% (94.4%–99.6%) | 69.9% | 90.9% | 1 |
| dry run max(50, 5% of review) | 93.5% | 57.0% | 3 | 99.2% (95.7%–99.9%) | 68.3% | 98.9% | 0 |
| dry run max(50, 8% of review) | 93.5% | 55.3% | 3 | 99.2% (95.7%–99.9%) | 65.5% | 98.9% | 0 |
| dry run max(50, 12% of review) | 98.6% | 52.7% | 0 | 99.2% (95.7%–99.9%) | 61.8% | 98.9% | 0 |
| dry run max(100, 3% of review) | 98.2% | 56.6% | 0 | 98.4% (94.4%–99.6%) | 69.5% | 90.9% | 1 |
| dry run max(100, 5% of review) | 98.6% | 53.7% | 0 | 99.2% (95.7%–99.9%) | 68.1% | 98.9% | 0 |
| dry run max(100, 8% of review) | 98.6% | 52.1% | 0 | 99.2% (95.7%–99.9%) | 65.5% | 98.9% | 0 |
| dry run max(100, 12% of review) | 98.6% | 49.9% | 0 | 99.2% (95.7%–99.9%) | 61.8% | 98.9% | 0 |
| knee (adjusted, min 150 read) | 100.0% | 18.5% | 0 | 100.0% (97.1%–100.0%) | 14.1% | 100.0% | 0 |
| target t=10 (mean of 20 samples) | 93.5% | 46.9% | 4 | 92.9% (87.1%–96.2%) | 34.9% | 90.9% | 2 |

## Per test topic

| Rule | `CD008170` | `CD008201` | `CD012223` | `CD012347` |
|---|--:|--:|--:|--:|
| fixed threshold (fitted on other reviews) | 99% / 36% | 100% / 91% | 100% / 95% | 100% / 84% |
| consecutive k=50 + floor | 99% / 36% | 100% / 91% | 100% / 94% | 100% / 84% |
| knee (adjusted, min 150 read) | 100% / 0% | 100% / 19% | 100% / 77% | 100% / 16% |
| target t=10 (mean of 20 samples) | 91% / 45% | 100% / 15% | 100% / 24% | 94% / 32% |

Cells are recall / WSS. WSS counts every record read, including the target method's random sample and every record without an abstract (always read, never ranked).

Fixed threshold and floor: 0.343, fitted on the development reviews.

## Leave one review out: rule chosen on the other reviews

The rule is chosen with the same criterion as above, but on all the other reviews, then
applied to the one left out. Nothing about the scored review is used to pick its rule.

| Review | Rule chosen on the others | recall | WSS | fixed threshold: recall | WSS |
|---|---|--:|--:|--:|--:|
| `CD005139` | dry run max(100, 5% of review) | 98.2% | 60.8% | 87.5% | 62.2% |
| `CD006715` | dry run max(100, 5% of review) | 100.0% | 5.4% | 100.0% | 72.5% |
| `CD008018` | dry run max(100, 5% of review) | 100.0% | 68.3% | 100.0% | 59.3% |
| `CD008170` | consecutive k=50 + floor | 98.9% | 37.2% | 98.9% | 37.2% |
| `CD008201` | dry run max(100, 3% of review) | 90.9% | 83.6% | 100.0% | 91.9% |
| `CD010526` | dry run max(100, 5% of review) | 100.0% | 45.4% | 100.0% | 50.8% |
| `CD010778` | dry run max(100, 5% of review) | 100.0% | 44.2% | 100.0% | 59.9% |
| `CD011436` | dry run max(100, 5% of review) | 96.0% | 36.3% | 96.0% | 47.7% |
| `CD011571` | dry run max(100, 5% of review) | 100.0% | 0.0% | 80.0% | 58.1% |
| `CD012223` | dry run max(100, 5% of review) | 100.0% | 90.9% | 100.0% | 95.0% |
| `CD012347` | dry run max(100, 5% of review) | 100.0% | 81.9% | 100.0% | 84.7% |
| `CD012930` | dry run max(100, 5% of review) | 98.0% | 26.0% | 88.0% | 46.1% |

```
chosen rule      recall 98.5% (95% CI 96.8%–99.3%, 400/406) · pooled WSS 55.2% · reviews below 95%: 1
fixed threshold  recall 93.8% (95% CI 91.1%–95.8%, 381/406) · pooled WSS 55.0% · reviews below 95%: 3
```
