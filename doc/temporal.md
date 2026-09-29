# Temporal challengers (SES & ARIMA)

Offline **per-key** time-series models on Rome **OMI mid** (€/m²/month), for this portfolio project.

Code: `ml/selection/series.py`, `ses.py`, `arima.py`, `select_ses.py`, `select_arima.py`.  
Serve champion stays tabular **HGB** — root [`README.md`](../README.md) § ML / MLOps.

---

## Evaluation contract

| Item | Choice |
|------|--------|
| Data | Same `features_latest.jsonl` (no second ETL) |
| Series key | `(zona_omi, tipologia, stato)` |
| Split | Last OMI semester = test; fit only on earlier rows |
| Task | **1-step** forecast of next mid |
| Naive | `y_hat =` last mid in train history (lag-1) |
| Filter | Drop keys with **multiple distinct mids in the same semester** (ambiguous OMI rows) |
| History | `min_len` default 20 semesters before scoring |

---

## SES — Simple Exponential Smoothing

### Idea

Keep a smoothed **level** `L_t`. The next forecast is that level. One main free parameter: `alpha`.

### Equations

**Level update** (after seeing mid `y_t` at semester `t`):

```text
L_t = alpha * y_t  +  (1 - alpha) * L_{t-1}
```

**1-step forecast** (what we score):

```text
y_hat_{t+1} = L_t
```

So the forecast is a weighted blend of the latest observation and the previous level.

### Parameters

| Symbol / name | Meaning | Range / notes |
|---------------|---------|----------------|
| `y_t` | Observed OMI mid at semester `t` (€/m²/month) | From the series history |
| `L_t` | Smoothed level after semester `t` | Same units as mid |
| `L_{t-1}` | Previous level | Seeded by statsmodels (`initialization_method="estimated"`) |
| `alpha` | Smoothing weight on the **latest** observation | In `(0, 1)` |
| `1 - alpha` | Weight on the previous level | Complement of `alpha` |
| `y_hat_{t+1}` | Forecast for the next semester | Equals `L_t` |

**How `alpha` behaves:**

- `alpha → 1` → almost **naive** (almost only last mid matters)
- `alpha → 0` → almost **constant** level (slow to react to changes)
- Middle values → smooth past noise, but can lag real jumps

**In this repo** (`ml/selection/ses.py`):

- `statsmodels` `SimpleExpSmoothing`
- `optimized=True` → `alpha` (and init) estimated **per key**
- Fit failure → fall back to last mid

### Command

```bash
.venv/bin/python -m ml.selection.select_ses --notes offline-ses
```

MLflow experiment: `roma-rent-ses-optimization`.

### Result here

On the clean series mask, SES MAE is **≈ naive** (slightly worse). Optimized `alpha` is often ≈ 1, so SES collapses toward lag-1; when `alpha` is lower it over-smooths sticky OMI series and loses MAE.

---

## ARIMA — AutoRegressive Integrated Moving Average

### Idea

Model a (possibly **differenced**) univariate series with three integers:

```text
ARIMA(p, d, q)
```

| Letter | Name | Role |
|--------|------|------|
| `p` | AR order | How many **past values** (of the differenced series) enter the equation |
| `d` | Integration / differencing | How many times to difference the series before fitting AR/MA |
| `q` | MA order | How many **past forecast errors** enter the equation |

### Differencing (`d`)

First difference (`d = 1`):

```text
Delta y_t  =  y_t - y_{t-1}
```

Higher `d` means differencing that series again. Differencing removes a slow drift so AR/MA can fit the **changes** instead of the raw €/m² level.

### General form (after `d` differences)

Let `z_t` be the series after `d` differences (`z_t = y_t` if `d = 0`). Then:

```text
z_t = c
      + phi_1 * z_{t-1} + ... + phi_p * z_{t-p}
      + e_t
      + theta_1 * e_{t-1} + ... + theta_q * e_{t-q}
```

Forecast = 1-step prediction of `y_{t+1}` (integrate / undo differencing if `d > 0`).

### Parameters

| Symbol / name | Meaning | Notes |
|---------------|---------|--------|
| `p` | Number of AR lags | Integer ≥ 0; CLI `--order p,d,q` |
| `d` | Differencing order | Integer ≥ 0; `0` = model the mid level; `1` = model Δ mid |
| `q` | Number of MA lags | Integer ≥ 0 |
| `c` | Constant / drift term | Estimated by statsmodels (may be 0 depending on order) |
| `phi_1 … phi_p` | AR coefficients | Weight of past `z` values |
| `theta_1 … theta_q` | MA coefficients | Weight of past errors |
| `e_t` | White-noise innovation at `t` | Residual / shock |
| `z_t` | Series after `d` differences | Equals `y_t` when `d = 0` |
| `y_t` | Observed mid | Target series |

**In this repo** (`ml/selection/arima.py`):

- Fixed `(p, d, q)` only (no auto-ARIMA)
- `enforce_stationarity=False`, `enforce_invertibility=False` (more fits on short series)
- Non-convergence / bad fit → last mid; `n_fallback` logged

### Command

```bash
.venv/bin/python -m ml.selection.select_arima --order p,d,q --notes offline-arima
```

MLflow experiment: `roma-rent-arima-optimization`.

---

## Cases we tried

All on the **same** clean mask (~1144 keys after dropping ambiguous series). Naive MAE ≈ **0.2965**.

### 1. ARIMA(1, 0, 0) — AR(1) on the **level**

```text
y_t = c + phi_1 * y_{t-1} + e_t
```

| Param | Value | Meaning here |
|-------|-------|----------------|
| `p` | 1 | One lag of the mid level |
| `d` | 0 | No differencing (model €/m² directly) |
| `q` | 0 | No MA term |
| `phi_1` | estimated | Autocorrelation of the level |

- **Result:** worse than naive (example `arima_mae ≈ 0.40`); many fragile fits on short series.

```bash
.venv/bin/python -m ml.selection.select_arima --order 1,0,0 --notes offline-arima-100
```

### 2. ARIMA(1, 1, 0) — AR(1) on **differences**

```text
(y_t - y_{t-1}) = c + phi_1 * (y_{t-1} - y_{t-2}) + e_t
```

| Param | Value | Meaning here |
|-------|-------|----------------|
| `p` | 1 | One lag of the **change** in mid |
| `d` | 1 | First difference |
| `q` | 0 | No MA term |
| `phi_1` | estimated | Autocorrelation of Δ mid |

- Models how the mid **changes**, then reconstructs the level.  
- Often a better default for prices than `(1,0,0)`.  
- **Result:** better than `(1,0,0)`, still **behind naive** (example `arima_mae ≈ 0.35`).

```bash
.venv/bin/python -m ml.selection.select_arima --order 1,1,0 --notes offline-arima-110
```

### 3. ARIMA(0, 1, 0) — random walk ≡ naive

```text
y_t = y_{t-1} + e_t

=>  y_hat_{t+1} = y_t     (last mid)
```

| Param | Value | Meaning here |
|-------|-------|----------------|
| `p` | 0 | No AR |
| `d` | 1 | Random-walk / first difference only |
| `q` | 0 | No MA |

- Optimal 1-step forecast = **last mid**.  
- **Result (observed):**

```text
n_tasks=1144  order=(0, 1, 0)  arima_mae=0.2965  naive_mae=0.2965
```

Equal MAE is **correct**, not a logging bug. Use this order as a **sanity check**: if it does not match naive, investigate series construction / leakage.

```bash
.venv/bin/python -m ml.selection.select_arima --order 0,1,0 --notes offline-arima-010
```

### Summary table

| Model | Intuition | vs naive (this data) |
|-------|-----------|----------------------|
| Naive (lag-1) | Repeat last mid | Baseline (best MAE) |
| SES | Smoothed level (`alpha`) | ≈ naive |
| ARIMA(1,0,0) | AR on level | Worse |
| ARIMA(1,1,0) | AR on Δ mid | Worse (less than 1,0,0) |
| ARIMA(0,1,0) | Random walk | **= naive** |

---

## Why persistence wins (~24 semesters)

1. OMI mids change slowly → lag-1 is already near-optimal for MAE.  
2. Short series → AR/MA (and even `alpha`) are hard to estimate stably.  
3. Per-key models do **not** see cross-zone structure (that is where panel HGB helps RMSE/R²).

So little “boost” from classical TS here is an empirical finding about the **data**, after fixing ambiguous keys—not a claim that SES/ARIMA are useless in general.

---

## What this does *not* mean

- Do **not** promote naive/SES/ARIMA to `baseline_latest` by default: serve needs the tabular HGB path (API features + TreeSHAP).  
- SES/ARIMA are **offline challengers** in MLflow, not CI / retrain.  
- Feature scaling for HGB is irrelevant to these univariate mid series.

---
