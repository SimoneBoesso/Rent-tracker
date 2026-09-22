# Postgres vs SQLite (sightings store)

Notes for choosing the **sightings** store in Roma Rent Monitor.  
Operational context: [`roadmap-naive-sightings-db.md`](roadmap-naive-sightings-db.md) (Phase 2 = **Postgres**).

MLflow stays on SQLite (`mlflow.db`) — local tracking, not shared API state.

---

## Problem with the current JSON approach

For each `POST /sightings` today typically:

1. **read** `seen.json` (local and/or R2)
2. **check** whether the digest already exists
3. if not → **append** to `sightings.jsonl` and **rewrite** `seen.json` (in cloud also get+put of the whole JSONL on R2)

There is no shared lock/transaction: two parallel requests can both see “not present yet” and both write → duplicates or overwrite on R2.

**Yes:** the file is read and written every time. **No:** concurrency is not handled.

A DB with `UNIQUE(digest)` + `INSERT … ON CONFLICT` moves check+insert into one atomic operation.

---

## Two roles: API vs database

| Role | What it does |
|------|----------------|
| **API** | Receives requests, runs predict, talks to the DB |
| **Database** | Holds data (sightings, digest uniqueness) |

User load is distributed across **API** instances. The DB is the **single source of truth** where all APIs read/write the same state.

---

## Persistence

| Store | Persistence |
|-------|-------------|
| **SQLite** | Yes: it is a **file** on disk. The risk on Render free is not SQLite itself, it is the **container disk** (ephemeral on redeploy). With a persistent disk, SQLite would survive too. |
| **Managed Postgres** | Data lives **outside** the API container → survives redeploys without mounting disk on the API. |

---

## Concurrency and multiple machines

### Postgres — multiple APIs, one DB

```text
  User1 ──┐
  User2 ──┼──► Load balancer ──► API #1 ──┐
  User3 ──┘                  └─► API #2 ──┼──► Postgres (one DB)
                                          └─► API #3 ──┘
```

- Multiple API machines in parallel, same `DATABASE_URL`.
- Safe dedupe with `UNIQUE(digest)`.
- Stopping/restarting one API does not delete sightings.

### SQLite — tied to one machine

```text
  User ──► API (one machine) ──► file sightings.sqlite
                 (on THAT machine's disk)
```

| Scenario (**API server** side — not where end users sit) | SQLite | Postgres |
|----------|--------|----------|
| Concurrent HTTP on the **same** API **process** (e.g. one uvicorn worker) | Ok (WAL + unique) | Ok |
| Multiple workers / processes on the **same** API machine, same file path | Possible; writes serialized | Ok |
| Multiple API **instances/hosts** (different machines) | No in practice (separate local files) | Yes, same `DATABASE_URL` |

Note: users on different PCs/phones hitting the **same** API fall under the first row (or the second if you run multiple workers on one host). The third row is when you scale **API machines**.

**Distributing load** = scale the **APIs**, not “shard” the DB. All APIs must see the **same** sightings and the same dedupe. Postgres allows that across machines; SQLite does not (without fragile tricks like a network filesystem).

---

## Postgres on multiple DB instances? (another level)

Yes, it *can*, but that is beyond the typical scope of this project:

| Pattern | What it does | When |
|--------|----------------|------|
| **Primary + read replica** | One writes; others serve `SELECT` | Heavy reads |
| **Failover / HA** | Standby if the primary dies | Reliability |
| **Sharding** | Data split across nodes | Huge volume |

For sightings, **one** managed Postgres (Render / Neon / local Docker) is enough. Add replica/HA only if load grows.

---

## Why Postgres in this repo (portfolio)

1. Multi-writer / multi-instance API concurrency.
2. Persistence on Render without depending on the API disk.
3. Simple queries (`SELECT` for drift / gap aggregates) instead of parsing JSONL.
4. Product-shaped story: FastAPI → Postgres → constraint → `DATABASE_URL`.

SQLite would be enough for a **single-instance** prototype with non-ephemeral disk; for portfolio and cloud deploy, Postgres is the choice fixed in the roadmap.

---

## Anti-goals

- Using Postgres for MLflow (stays SQLite).
- Sharding / multi-primary cluster for a small sightings N.
- Keeping R2 as a parallel write-path for sightings (reintroduces races): write only to Postgres.
