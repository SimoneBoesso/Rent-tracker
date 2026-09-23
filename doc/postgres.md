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

## Cloud (Render) — deploy checklist

You do **not** run a second Docker “postgres” container. Render provides **managed PostgreSQL**; the existing **API** Web Service connects via `DATABASE_URL`.

Full stack deploy notes: [`render.md`](render.md).

### 0. Code on GitHub

Working tree clean and pushed to `main` (Postgres store + dashboard address fields). Then Render can deploy the latest commit.

### 1. Create Postgres (managed)

1. Open [dashboard.render.com](https://dashboard.render.com)
2. **New +** → **PostgreSQL**
3. Name: e.g. `rent-tracker-pg`
4. **Region:** same as the API service
5. Plan: Free / Starter if available → **Create Database**
6. Wait until status is **Available**
7. Open the DB page → copy **Internal Database URL**  
   (preferred when API and DB share a region; use External only if you must connect from outside Render)

If the URL starts with `postgres://`, rewrite as `postgresql://` (same user/host/path) for **psycopg**.

### 2. Attach `DATABASE_URL` to the API

1. Render → open the **API** Web Service (Docker), **not** the Streamlit UI
2. **Environment** → **Add Environment Variable**
3. Key: `DATABASE_URL`  
   Value: URL from step 1 (do not commit this string to git)
4. **Save Changes** (usually triggers a redeploy)

Do **not** set `DATABASE_URL` on the UI service — the UI only calls the API via `RENT_API_URL`.

### 3. Redeploy services

1. API service → **Manual Deploy** → **Deploy latest commit** (if Save did not already redeploy)
2. UI service → **Manual Deploy** (needed for listing form fields: comune / CAP / via / civico)

Schema is created on first successful `POST /sightings` (`CREATE TABLE IF NOT EXISTS`).

### 4. Smoke (live)

Cold start on free tier can be slow — hit `/health` first.

```bash
curl -s https://<api-service>.onrender.com/health

curl -s https://<api-service>.onrender.com/sightings -H 'Content-Type: application/json' \
  -d '{"zona_omi":"B12","tipologia":"Abitazioni civili","stato":"NORMALE","asking_eur_m2":18.0,"comune":"Roma","cap":"00153","via":"Via Roma","civico":"5"}'
```

Expect JSON with `"status":"ok"` (or `"duplicate"` on a second identical address).  
If the env is missing, the handler fails when opening Postgres — check API env and logs.

UI: fill **comune / CAP / via / civico**, then Submit (geocode address line is only for zona prefill).

### 5. Inspect rows (local + cloud)

Data lives in table `sightings`. You do **not** need the Render CLI (`render` is not installed via `apt`; ignore suggestions like `raster3d`).

**Local Docker**

```bash
docker exec -it rent-pg psql -U postgres -d rent -c \
  "SELECT sighting_id, via, civico, asking_eur_m2, submitted_at FROM sightings ORDER BY submitted_at DESC LIMIT 20;"
```

**Cloud (Render) — fastest without installing `psql`**

1. Render → your **PostgreSQL** → copy **External Database URL**  
2. If it starts with `postgres://`, change to `postgresql://`  
3. Use the project venv (`psycopg` already in `requirements.txt`):

```bash
export DATABASE_URL='postgresql://…'   # paste External URL; do not commit

.venv/bin/python -c "
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as c:
    with c.cursor() as cur:
        cur.execute('''
          SELECT sighting_id, via, civico, asking_eur_m2, submitted_at
          FROM sightings
          ORDER BY submitted_at DESC
          LIMIT 20
        ''')
        for row in cur.fetchall():
            print(row)
"
```

If you see `relation "sightings" does not exist`, no live `POST /sightings` has run yet (schema is created on first write).

**Optional: install `psql`**

```bash
sudo apt install postgresql-client
psql "$DATABASE_URL" -c "SELECT count(*) FROM sightings;"
```

GUI alternatives: DBeaver / TablePlus / pgAdmin with the same External URL.

List Render **services** (API, UI, Postgres): [dashboard.render.com](https://dashboard.render.com) — no CLI required.

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
