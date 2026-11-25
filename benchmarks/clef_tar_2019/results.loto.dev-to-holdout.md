# Screening with thresholds fitted on other reviews

Recall target 95% · fitted once on the 8 development topics (`--criteria v2` dumps), applied to every other topic.

| Topic | Records | Eligible | own threshold (optimistic) | recall | WSS | pooled threshold | recall | WSS | min threshold | recall | WSS |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `CD008170` | 12,319 | 88 | 0.865 | 95.5% | 67.8% | 0.235 | 98.9% | 20.0% | 0.108 | 98.9% | 2.6% |
| `CD008201` | 3,574 | 11 | 0.554 | 100.0% | 95.3% | 0.235 | 100.0% | 81.5% | 0.108 | 100.0% | 51.9% |
| `CD012223` | 2,456 | 12 | 0.383 | 100.0% | 95.8% | 0.235 | 100.0% | 93.4% | 0.108 | 100.0% | 83.4% |
| `CD012347` | 1,098 | 16 | 0.467 | 100.0% | 92.5% | 0.235 | 100.0% | 81.6% | 0.108 | 100.0% | 50.6% |

```
own (optimistic)  recall 96.9% (95% CI 92.2%–98.8%, 123/127) · pooled WSS 77.5%
pooled            recall 99.2% (95% CI 95.7%–99.9%, 126/127) · pooled WSS 44.0%
min               recall 99.2% (95% CI 95.7%–99.9%, 126/127) · pooled WSS 24.5%
```

## Calibration of the eligibility score (tested topics, judged records)

Brier 0.205 · ECE 0.339

| Score bin | Records | Mean score | Share eligible |
|---|--:|--:|--:|
| 0.0–0.1 | 4,646 | 0.048 | 0.000 |
| 0.1–0.2 | 3,065 | 0.148 | 0.000 |
| 0.2–0.3 | 2,524 | 0.247 | 0.000 |
| 0.3–0.4 | 1,798 | 0.347 | 0.001 |
| 0.4–0.5 | 1,271 | 0.445 | 0.002 |
| 0.5–0.6 | 885 | 0.548 | 0.003 |
| 0.6–0.7 | 609 | 0.648 | 0.003 |
| 0.7–0.8 | 586 | 0.750 | 0.003 |
| 0.8–0.9 | 777 | 0.854 | 0.014 |
| 0.9–1.0 | 1,855 | 0.950 | 0.056 |

The eligibility score combines the criteria's probabilities; it is not a calibrated probability of inclusion, so a gap here is expected and is what a threshold fitted on labels corrects for.
