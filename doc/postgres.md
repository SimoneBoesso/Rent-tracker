# Postgres (sightings store)

Operational setup for the **user listings** store.  
Why Postgres (not SQLite): [`postgres-vs-sqlite.md`](postgres-vs-sqlite.md).  
Feature / checklist: [`roadmap-postgres-intro.md`](roadmap-postgres-intro.md).  
API details + digest rules: [`usage.md`](usage.md). Deploy overview: [`render.md`](render.md).

**Product rule:** baseline train stays on **OMI mid**. Sightings = asking gap signal only.  
MLflow stays on **SQLite** (`mlflow.db`) — do **not** point MLflow at this Postgres.  
Cite: «Agenzia Entrate – OMI».

---

## What talks to Postgres

| Piece | Role |
|-------|------|
| FastAPI `POST /sightings` | Insert / dedupe via `UNIQUE(digest)` |
| `api/sightings_db.py` | Schema + `INSERT … ON CONFLICT` |
| `ml.sightings_drift_report` | Reads rows when `DATABASE_URL` is set |
| Streamlit UI | Sends `comune` / `cap` / `via` / `civico` + OMI fields |

The app never hardcodes host: it only reads **`DATABASE_URL`**.

```text
Local:   API ──► Docker postgres:16 (127.0.0.1:5432)
Render:  API ──► managed PostgreSQL (same env name DATABASE_URL)
```

Legacy JSONL / R2 `sightings-inbox/` is **not** a write path anymore (removed; no migration).

---

## Local (Docker)

### 1. Start Postgres

```bash
docker run -d --name rent-pg \
  -e POSTGRES_PASSWORD=rent \
  -e POSTGRES_DB=rent \
  -p 5432:5432 \
  postgres:16
```

If the container already exists: `docker start rent-pg`.

### 2. Env + dependency

```bash
export DATABASE_URL=postgresql://postgres:rent@127.0.0.1:5432/rent
# psycopg[binary] is in requirements.txt
source .venv/bin/activate
pip install -r requirements.txt
```

Smoke:

```bash
.venv/bin/python -c "
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as c:
    with c.cursor() as cur:
        cur.execute('SELECT 1')
        print(cur.fetchone())
"
```

### 3. Run API (same shell — so it sees `DATABASE_URL`)

```bash
.venv/bin/uvicorn api.main:app --reload --port 8000
```

Schema is created on first sighting write (`CREATE TABLE IF NOT EXISTS`).

### 4. Smoke sighting

```bash
curl -s http://127.0.0.1:8000/sightings -H 'Content-Type: application/json' \
  -d '{"zona_omi":"B12","tipologia":"Abitazioni civili","stato":"NORMALE","asking_eur_m2":18.0,"comune":"Roma","cap":"00153","via":"v. Roma","civico":"05"}'
```

Second POST with same dwelling (`Via Roma` / `5`, different asking) → `"status":"duplicate"`.

### 5. Tests that need the DB

```bash
export DATABASE_URL=postgresql://postgres:rent@127.0.0.1:5432/rent
.venv/bin/python -m pytest tests/test_sighting.py tests/test_sighting_digest.py -q
```

Without `DATABASE_URL`, PG integration tests **skip**; digest unit tests still run.

---

## Cloud (Render)

You do **not** run a second Docker “postgres” container yourself. Render provides a **managed PostgreSQL**; the existing **API** Web Service connects via env.

### 1. Push code

Commit/push the Postgres + UI changes, then Manual Deploy API (and UI if `dashboard/` changed).

### 2. Create the database

1. Render Dashboard → **New +** → **PostgreSQL**  
2. Create (free/starter as available)  
3. Open the DB → copy **Internal Database URL** (preferred for the API on the same region) or External if needed  

If the URL starts with `postgres://`, change it to `postgresql://` (same rest of the string) for psycopg.

### 3. Wire the API service

1. Open the **API** (Docker) Web Service  
2. **Environment** → **Add**  
   - Key: `DATABASE_URL`  
   - Value: the URL from step 2  
3. Save (triggers redeploy)  

Do **not** put `DATABASE_URL` on the Streamlit UI service — the UI only calls the API (`RENT_API_URL`).

### 4. Verify

```bash
curl -s https://<api-service>.onrender.com/health
curl -s https://<api-service>.onrender.com/sightings -H 'Content-Type: application/json' \
  -d '{"zona_omi":"B12","tipologia":"Abitazioni civili","stato":"NORMALE","asking_eur_m2":18.0,"comune":"Roma","cap":"00153","via":"Via Roma","civico":"5"}'
```

Expect `status: ok` (or `duplicate` on repeat). Cold start on free tier can be slow — hit `/health` first.

UI: fill **comune / CAP / via / civico** on the listing form, then Submit (geocode address is only for zona prefill).

---

## Digest reminder (dedupe key)

Normalized `comune|cap|via|civico` → SHA-256.  
`piano` / `interno` / listing / asking are **not** in the key.  
Full rules: [`usage.md`](usage.md) § Sightings store.

---

## Checklist (done in this slice)

- [x] Local Docker + `DATABASE_URL` + `psycopg`  
- [x] Address digest + table `sightings` + API wire  
- [x] Tests (skip without DB) + drift from PG  
- [x] Legacy JSONL/R2 sightings removed (no migrate)  
- [x] Docs (usage / render / README)  
- [ ] **Your ops:** create Render Postgres + set `DATABASE_URL` + redeploy + smoke live  

---

## Anti-goals

- SQLite for sightings  
- Postgres for MLflow  
- R2 / JSONL as a second write-path for sightings  
- Putting `DATABASE_URL` only on the UI service  
