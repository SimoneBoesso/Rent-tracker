# Roadmap: introdurre Postgres (Feature B — slice)

Learning plan operativo per sostituire `sightings.jsonl` + `seen.json` (+ R2) con **Postgres**.  
Contesto completo (geo A + Feature B): [`roadmap-naive-sightings-db.md`](roadmap-naive-sightings-db.md).  
Perché Postgres (non SQLite): [`postgres-vs-sqlite.md`](postgres-vs-sqlite.md).  
Setup locale + cloud (Render): [`postgres.md`](postgres.md).

**Product rule:** baseline resta su **OMI mid**. Sightings = secondo segnale (asking gap), non target di train.  
Cite: «Agenzia Entrate – OMI».

**Pair programming:** quando scrivi **`ora`** in chat → review del codice appena scritto rispetto a questa roadmap (vedi `.cursor/rules/ora-code-review.mdc`).

---

## Perché

Oggi ogni `POST /sightings` tipicamente: read `seen.json` → check digest → append JSONL / rewrite seen (in cloud anche get+put R2). Niente lock → race sotto concurrency.

Postgres con `UNIQUE(digest)` + `INSERT … ON CONFLICT` fa check+insert in un’operazione atomica.

Contratto HTTP da **non rompere:** `append_sighting` → `("ok"|"duplicate", id)`; response `status` / `duplicate_of`.

```mermaid
flowchart LR
  POST["POST_/sightings"] --> Norm["normalize_address"]
  Norm --> Dig["SHA256_digest"]
  Dig --> PG["INSERT_ON_CONFLICT"]
  PG -->|inserted| Ok["status_ok"]
  PG -->|conflict| Dup["status_duplicate"]
```

---

## Scelte fissate

| Decisione | Scelta |
|-----------|--------|
| Store | Postgres via `DATABASE_URL`, driver **psycopg** (v3) |
| Tabella | `sightings` + `UNIQUE(digest)` |
| Dev locale | Docker `postgres:16` su `127.0.0.1:5432` |
| Produzione | Managed (Render Postgres / Neon); **stesso** env `DATABASE_URL`, host diverso |
| Legacy JSONL | PG vuoto in dev (policy c); non migrare senza indirizzo in questo slice |
| Chiave digest | `comune\|cap\|via\|civico` — `piano` / `interno` **fuori** |
| Hash | SHA-256 |
| MLflow | Resta SQLite (`mlflow.db`) — non mescolare |
| Scope slice | Setup → normalize+digest → 2.1 store → 2.2 wire → test. Drift/migrate/doc dopo |

---

## Checklist

- [x] **0** Setup: Docker PG + `DATABASE_URL` + `psycopg` in `requirements.txt`
- [x] **1** Normalizzazione indirizzo + nuovo `sighting_digest` (unit test puri)
- [x] **2.1** `api/sightings_db.py`: connect, `init_schema`, insert ON CONFLICT, `get_by_digest`
- [x] **2.2** Wire `append_sighting` + body indirizzo/listing; niente JSONL/`seen`/R2 write-path
- [x] **2.5** Test su digest/DB (skip se no `DATABASE_URL`)
- [x] **2.3** Drift da Postgres (`DATABASE_URL`; JSONL solo fallback legacy)
- [x] **2.4** Skip migrate — nessun annuncio legacy da tenere; JSONL/R2 sightings rimossi (policy c)
- [x] **2.6** usage / render / README (sightings → Postgres, digest rules, `DATABASE_URL`)

---

## Step 0 — Setup (non codice app)

Solo per **sviluppare in locale** (non è il DB di produzione):

```bash
docker run -d --name rent-pg -e POSTGRES_PASSWORD=rent -e POSTGRES_DB=rent \
  -p 5432:5432 postgres:16
export DATABASE_URL=postgresql://postgres:rent@127.0.0.1:5432/rent
```

Aggiungere `psycopg[binary]` a `requirements.txt`. Smoke: connect con `psycopg`.

In deploy (Render): Postgres managed → stessa variabile `DATABASE_URL` sul servizio API. Dettaglio in step 2.6 / [`render.md`](render.md).

**Done when:** `DATABASE_URL` usabile; `import psycopg` ok.

---

## Step 1 — Normalizzazione + digest (prima di PG)

Helper puri (es. `api/sighting_digest.py` o in `api/sightings.py`):

| Regola | Nota |
|--------|------|
| Trim + collasso spazi | `" Via Roma "` → forma stabile |
| Lowercase | case-insensitive |
| Punteggiatura non significativa | punti/virgole inutili |
| Abbreviazioni | `v.` → `via`, `c.so` → `corso`, `p.zza` → `piazza` |
| Civico | `"05"` / `"5 "` → stessa forma |
| Accenti | fold se serve (`à` → `a`) |

1. Normalizza `comune`, `cap`, `via`, `civico`.
2. Concatena con `|` (ordine fisso).
3. SHA-256 → `digest`.

**Sostituisce** l’hash attuale su `zona_omi|tipologia|stato|asking` in [`api/sightings.py`](../api/sightings.py).

**Done when:** `"Via Roma"` vs `"v. Roma"` → stesso digest; asking/listing diversi non cambiano il digest.

---

## Step 2.1 — Store sottile

Modulo `api/sightings_db.py`:

- `connect()` da `DATABASE_URL` (mancante → errore chiaro)
- `init_schema()` — `CREATE TABLE IF NOT EXISTS sightings` (OMI/predict + indirizzo + listing nullable + `digest UNIQUE`)
- `insert_sighting` — `INSERT … ON CONFLICT (digest) DO NOTHING`; conflict → `get_by_digest` → `("duplicate", sighting_id)`

Tipi: text indirizzo; int bagni/locali/piano; numeric `mq`; bool amenity. Indirizzo minimo per digest: `comune`, `cap`, `via`, `civico`.

**Done when:** due insert stesso digest → **una** riga.

---

## Step 2.2 — Wiring API

- Estendere `SightingCreate` in [`api/main.py`](../api/main.py): indirizzo **obbligatorio**; listing opzionale; `interno` opz.
- `append_sighting`: digest da indirizzo → store PG → **niente** JSONL / `seen.json` / R2.
- Preservare `("ok"|"duplicate", id)`.

**Done when:** due POST stesso immobile, testo “sporco” diverso → secondo `duplicate`.

---

## Step 2.5 — Test

Aggiornare [`tests/test_sighting.py`](../tests/test_sighting.py): non contare linee JSONL.

- Unit normalize/digest (sempre, no DB)
- Integration: skip se `DATABASE_URL` assente
- Concorrenza: UNIQUE vince → 1 riga

---

## Dopo questo slice

| Step | Cosa |
|------|------|
| 2.3 | [`ml/sightings_drift_report.py`](../ml/sightings_drift_report.py) legge da PG |
| 2.4 | Migrazione one-shot JSONL → PG (policy legacy documentata) |
| 2.6 | [`usage.md`](usage.md), [`render.md`](render.md), README “sightings → Postgres” |

---

## Anti-goal

- SQLite per sightings; Postgres per MLflow
- ORM / Alembic
- Breaking `status` / `duplicate_of`
- R2 come secondo write-path
- `piano` in chiave senza dati affidabili
- Listing/indirizzo come target retrain OMI
- Dedupe ancora su OMI+asking

---

## File toccati (slice)

| File | Ruolo |
|------|--------|
| `requirements.txt` | `psycopg` |
| `api/sighting_digest.py` (o helper in `sightings.py`) | normalize + digest |
| `api/sightings_db.py` | schema + insert conflict |
| `api/sightings.py` | `append_sighting` → PG |
| `api/main.py` | body indirizzo/listing |
| `tests/test_sighting.py` | assert su digest/DB |

---

## Progress log

| Date | Note |
|------|------|
| 2026-09-23 | Doc slice intro Postgres (learning plan da pair session). Docker locale + managed via `DATABASE_URL`. Convenzione chat: `ora` → code review. |
| 2026-09-23 | Slice chiuso: digest + PG store + wire + test + drift da PG; legacy JSONL/R2 rimossi; doc 2.6. |
