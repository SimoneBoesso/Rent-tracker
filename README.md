# Rent-tracker

**Roma Rent Monitor** — official OMI fair rent (€/m²/month) for Rome: zone/typology history, next-semester forecast, listing sightings with address→zone, and drift/retrain monitoring.

[![CI](https://github.com/SimBoex/Rent-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/SimBoex/Rent-tracker/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

## Demo / live

**Live UI (Streamlit):** [rent-tracker-ui-service.onrender.com](https://rent-tracker-ui-service.onrender.com) — deploy in [`doc/render.md`](doc/render.md).

<video src="assets/RentTracker.webm" controls width="100%" title="Roma Rent Monitor — Streamlit UI demo">
  <a href="assets/RentTracker.webm">Download the UI walkthrough (WebM)</a>
</video>

*OMI profile history · fair €/m² forecast · address → zona OMI · listing sightings · drift / retrain*

**Docs:** [`doc/omi.md`](doc/omi.md) · [`doc/usage.md`](doc/usage.md) · [`doc/nominatim.md`](doc/nominatim.md) · [`doc/drift.md`](doc/drift.md) · [`doc/render.md`](doc/render.md) · [`doc/dvc.md`](doc/dvc.md) · [`doc/roadmap-naive-sightings-db.md`](doc/roadmap-naive-sightings-db.md) · [`doc/roadmap-learning.md`](doc/roadmap-learning.md) · [`doc/postgres-vs-sqlite.md`](doc/postgres-vs-sqlite.md).

## What it does

Rome **OMI** quotazioni (Agenzia delle Entrate) give zone-level €/m²/month bands by typology and condition, by semester — useful official benchmarks, hard to explore over time or turn into a forward estimate.

This project:

1. Loads OMI locazione CSVs → features → trains a fair €/m² model (OMI mid).
2. Serves **FastAPI** + **Streamlit**: profile history, predict / listing sighting, monitoring.
3. Optional **asking €/m²** the user saw on a portal → gap + deal label vs OMI band (or ±10% vs model). No portal scrape.
4. **Address → zona OMI**: Nominatim geocode + point-in-polygon on Roma boundaries (`H501`).
5. Drift / retrain gate and admin OMI ingest (DVC / R2).

Cite in UI/docs: «Agenzia Entrate – OMI».

## Architecture

```mermaid
flowchart LR
  A["OMI CSV\n+ H501 KML"] --> B["etl omi_loader\n+ coordinates"]
  B --> C["features_latest\n+ boundaries GeoJSON"]
  C --> D["ml.train\n+ MLflow"]
  D --> E["models/baseline_latest"]
  E --> F["FastAPI"]
  C --> F
  F --> G["Streamlit UI"]
  C --> H["drift_report"]
  H --> I["retrain_check"]
  I -->|should_retrain| D
  Addr[address] --> Nom[Nominatim]
  Nom --> F
```

| Layer | Role |
|-------|------|
| **ETL** | OMI VALORI/ZONE → JSONL features; KML → GeoJSON zones (`CODZONA` → `zona_omi`) |
| **ML** | `HistGradientBoostingRegressor`; temporal split by semester; MLflow |
| **API** | `/predict`, `/sightings`, `/profile/history`, `/meta/zones`, `/meta/zona-from-point`, `/ingest/omi` |
| **UI** | Profile overlays, listing form (address resolve + select override), monitoring |
| **Data** | Raw OMI + GeoJSON via **DVC → R2** (not in public git) |

- **Local:** `run_pipeline.py` = load → features → train (`--skip-train` / `--no-mlflow` optional).
- **CI** (`omi-monitoring`): ingest inbox → pipeline `--skip-train` → drift → retrain gate → snapshots.

## Model results

From `models/baseline_latest/metrics.json` (test = last OMI semester). **Naive** = prior-semester mid (`loc_mid_lag`).

| Metric | HGB | Naive |
|--------|-----|-------|
| **MAE** (€/m²/month) | 0.4892 | **0.4626** |
| **RMSE** | **1.1733** | 1.3588 |
| **R²** | **0.9610** | 0.9477 |
| **N** | **16 156** | |
| Train / test | 14 811 / 1 345 | |
| Features | `loc_mid_lag`, `zona_omi`, `tipologia`, `stato` | |
| Target | OMI mid `(loc_min + loc_max) / 2` | |

Lag-1 naive wins MAE on this split; HGB still improves RMSE/R² via cross-zone structure.

## Tech stack

Python **3.12** · scikit-learn · pandas · GeoPandas / Shapely · FastAPI · Streamlit · MLflow · Evidently · SHAP · DVC + boto3 (R2) · Docker · GitHub Actions · Render

## Setup / Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Place OMI `*VALORI*.csv` (and optional boundaries) under `data/raw/omi/` — see [`doc/omi.md`](doc/omi.md). Then:

```bash
.venv/bin/python run_pipeline.py -v
.venv/bin/uvicorn api.main:app --reload --port 8000
export RENT_API_URL=http://127.0.0.1:8000
.venv/bin/streamlit run dashboard/app.py
.venv/bin/python -m pytest -q
```

Useful curls:

```bash
# Fair rent + optional asking
curl -s http://127.0.0.1:8000/predict -H 'Content-Type: application/json' -d '{
  "zona_omi": "B12",
  "tipologia": "Abitazioni civili",
  "stato": "NORMALE",
  "loc_mid_lag": 20.0,
  "price_per_m2_monthly": 18.0
}'

# Point → zona OMI (needs boundaries via local file or DVC/R2)
curl -s 'http://127.0.0.1:8000/meta/zona-from-point?lat=41.88036&lon=12.46302'
```

MLflow: `.venv/bin/mlflow ui --backend-store-uri sqlite:///$(pwd)/mlflow.db --port 5000`

More commands: [`doc/usage.md`](doc/usage.md). Deploy: [`doc/render.md`](doc/render.md). Data sync: [`doc/dvc.md`](doc/dvc.md).

## Drift & retrain

1. **`ml.drift_report`** — Evidently `DataDriftPreset` (reference vs current semester split) → `reports/drift_latest/`.
2. **`ml.retrain_check`** — retrain if `mae_current / mae_reference ≥ 1.5` and `n_reference ≥ 50` (see [`doc/drift.md`](doc/drift.md)).

## Repository layout

```text
Rent-tracker/
├── api/              # FastAPI (+ boundaries PIP, sightings, ingest)
├── dashboard/        # Streamlit (+ Nominatim geocode)
├── data/             # raw/omi + processed (DVC; gitignored dumps)
├── doc/              # operational + roadmap docs
├── etl/              # omi_loader, omi_features, coordinates_loader
├── ml/               # train, drift, retrain
├── models/           # baseline_latest (baked in API image)
├── reports/          # drift / retrain / public snapshots
├── tests/
├── run_pipeline.py
├── Dockerfile
└── requirements.txt
```

## Next (roadmap)

Feature A (OMI perimeters → zona from address) is **done**. Next: sighting **address digest** + Postgres store — [`doc/roadmap-naive-sightings-db.md`](doc/roadmap-naive-sightings-db.md).
