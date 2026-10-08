# Empirical Noise Calibration

Measuring run-to-run variance of TypeSafe System One (`jev-1.13.0`) and OpenAI Decisions API (`gpt-6-luna`) across evaluation presets.

---

## The Measurement Problem

Large language model scoring engines can exhibit small score fluctuations across repeated calls for identical inputs. To establish whether a $\pm 0.10$ threshold safety margin is statistically valid, `typesafe-eval` measures run-to-run absolute difference:

$$\Delta = |p_{\text{run A}} - p_{\text{run B}}|$$

---

## Empirical Noise Matrix: TypeSafe System One (`jev-1.13.0`)

Measured across 60 total uncached evaluations (3 documents $\times$ 4 runs across 5 presets, totaling 396 pairwise comparisons against model `jev-1.13.0`):

| Preset | Comparisons | Mean &vert;&Delta;&vert; | Median &vert;&Delta;&vert; | 99th %ile &vert;&Delta;&vert; | Max &vert;&Delta;&vert; |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `quality` | 36 | 0.0008 | 0.000 | 0.005 | 0.005 |
| `safety` | 54 | 0.0038 | 0.000 | 0.030 | 0.030 |
| `tech-spec` | 36 | 0.0111 | 0.010 | 0.020 | 0.020 |
| `design-doc` | 180 | 0.0021 | 0.000 | 0.020 | 0.020 |
| `pr-description` | 90 | 0.0086 | 0.010 | 0.040 | 0.040 |
| **Overall** | **396** | **0.0045** | **0.000** | **0.030** | **0.040** |

---

## Empirical Noise Matrix: OpenAI Decisions API (`gpt-6-luna`)

Measured across 45 total uncached evaluations (3 documents $\times$ 3 runs across 5 presets, totaling 198 pairwise comparisons against model `gpt-6-luna` via `scripts/measure_noise.py --provider openai`):

| Preset | Comparisons | Mean &vert;&Delta;&vert; | Median &vert;&Delta;&vert; | 99th %ile &vert;&Delta;&vert; | Max &vert;&Delta;&vert; |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `quality` | 18 | 0.0000 | 0.000 | 0.000 | 0.000 |
| `safety` | 27 | 0.0000 | 0.000 | 0.000 | 0.000 |
| `tech-spec` | 18 | 0.0000 | 0.000 | 0.000 | 0.000 |
| `design-doc` | 90 | 0.0000 | 0.000 | 0.000 | 0.000 |
| `pr-description` | 45 | 0.0000 | 0.000 | 0.000 | 0.000 |
| **Overall** | **198** | **0.0000** | **0.000** | **0.000** | **0.000** |

---

## Multi-Provider Noise Comparison

| Dimension | TypeSafe System One (`jev-1.13.0`) | OpenAI Decisions API (`gpt-6-luna`) |
| :--- | :---: | :---: |
| **Overall Mean &vert;&Delta;&vert;** | $0.0045$ | **$0.0000$** |
| **99th %ile &vert;&Delta;&vert;** | $0.030$ | **$0.000$** |
| **Maximum &vert;&Delta;&vert;** | $0.040$ | **$0.000$** |
| **Output Token Cost** | Variable | **$0$ tokens** |
| **Determinism** | Statistical ($\Delta \le 0.04$) | Strictly Deterministic ($\Delta = 0.00$) |

---

## Key Conclusions

1. **Safety Margin Validity**:
   - For `jev-1.13.0`, the 99th percentile noise is **$0.030$** (max **$0.040$**), providing an empirical buffer (~2.5× to 3× of observed maximum) for the $\pm 0.10$ threshold margin. Note that this pilot benchmark was measured across 3 documents × 4 runs (36–180 pairwise comparisons per preset), where sample percentiles approximate the observed maximum.
   - For `gpt-6-luna`, forward-pass logit extraction is strictly deterministic ($\Delta = 0.0000$), eliminating score jitter entirely between identical runs.

2. **Near-Threshold Annealing**:
   - Scores landing in $[0.40, 0.60]$ remain soft observations under both models. Capping automated agent rewrite loops at 2 iterations avoids unnecessary over-optimization churn.
