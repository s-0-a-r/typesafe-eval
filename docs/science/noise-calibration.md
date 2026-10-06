# Empirical Noise Calibration

Measuring run-to-run variance of TypeSafe System One (Jev-1.13.0) across evaluation presets.

---

## The Measurement Problem

Large language model scoring engines can exhibit small score fluctuations across repeated calls for identical inputs. To establish whether a $\pm 0.10$ threshold safety margin is statistically valid, `typesafe-eval` measures run-to-run absolute difference:

$$\Delta = |p_{\text{run A}} - p_{\text{run B}}|$$

---

## Empirical Noise Matrix (Measured 2026-10-06)

Across 60 total uncached evaluations (3 documents $\times$ 4 runs across 5 presets, totaling 396 pairwise comparisons against model `jev-1.13.0`):

| Preset | Comparisons | Mean &vert;&Delta;&vert; | Median &vert;&Delta;&vert; | 99th %ile &vert;&Delta;&vert; | Max &vert;&Delta;&vert; |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `quality` | 36 | 0.0008 | 0.000 | 0.005 | 0.005 |
| `safety` | 54 | 0.0038 | 0.000 | 0.030 | 0.030 |
| `tech-spec` | 36 | 0.0111 | 0.010 | 0.020 | 0.020 |
| `design-doc` | 180 | 0.0021 | 0.000 | 0.020 | 0.020 |
| `pr-description` | 90 | 0.0086 | 0.010 | 0.040 | 0.040 |
| **Overall** | **396** | **0.0045** | **0.000** | **0.030** | **0.040** |

---

## Key Conclusions

1. **Safety Margin Validity**:
   - The observed overall 99th percentile noise is **$0.030$**, and the absolute maximum delta observed across all 396 comparisons is **$0.040$**.
   - Because noise remains well under $\pm 0.10$, the threshold boundary margin of $\pm 0.10$ provides a statistically robust buffer (>2.5× to 3× empirical noise) ensuring that true passes do not randomly fluctuate into hard CI gate failures.

2. **Near-Threshold Annealing**:
   - Scores landing in $[0.40, 0.60]$ are soft observations. If an autonomous agent optimizes text that is already at $0.48$, minor noise could cause oscillations. Capping agent rewrite loops at 2 iterations avoids churn.
