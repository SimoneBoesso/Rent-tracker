# Nominatim (geocoding)

**Nominatim** is the free geocoder of [OpenStreetMap](https://www.openstreetmap.org/).  
It turns a human address (or place name) into **latitude / longitude** (and the reverse).

It does **not** know OMI zones. Zone codes (`zona_omi`) come only from our point-in-polygon on OMI boundaries (`H501` KML/GeoJSON) — see [`omi.md`](omi.md) and Feature A in [`roadmap-naive-sightings-db.md`](roadmap-naive-sightings-db.md).

## Role in this project (G4)

Sighting / predict UX:

1. User types an **address** (e.g. a listing street in Rome).
2. **Nominatim** → `(lat, lon)`.
3. Our API / helper → `zona_omi` via PIP on `data/processed/omi/boundaries/H501.geojson` (from `H501.kml`).
4. UI **prefills** the zone select; the user can still override manually.

```text
address  →  Nominatim  →  lat, lon  →  OMI PIP  →  zona_omi
                ↑                         ↑
         OpenStreetMap              Agenzia Entrate – OMI
```

Geocode and OMI perimeters stay **separate**: Nominatim never returns `C12` / `B12`; we resolve that ourselves.

## Public API (search)

Base URL: `https://nominatim.openstreetmap.org/search`

Typical query params:

| Param | Meaning |
|-------|---------|
| `q` | Free-text address |
| `format` | `json` |
| `limit` | Prefer `1` for a single best hit |
| `countrycodes` | Optional bias, e.g. `it` |
| `viewbox` / `bounded` | Optional bbox around Rome to prefer local results |

Example (illustrative):

```bash
curl -s -H 'User-Agent: Rent-tracker/0.1 (local-dev)' \
  'https://nominatim.openstreetmap.org/search?q=Via%20Carini%2045%20Roma&format=json&limit=1&countrycodes=it'
```

Useful fields in each hit: `lat`, `lon`, `display_name`.

## Usage rules (required)

Nominatim’s public instance expects fair use. For this app:

- Send a clear **`User-Agent`** (app name + contact or repo), not a generic browser string.
- Stay around **≤ 1 request/second**; do not bulk-geocode without your own instance.
- Prefer caching identical addresses in-session (Streamlit `session_state`) so “Resolve zone” is not spammed.
- On empty / failed geocode → show an error and keep the **manual zone select**.

Official policy: [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).

## Where it lives in code (target)

| Piece | Responsibility |
|-------|----------------|
| Dashboard helper (`httpx`) | Call Nominatim; return `(lat, lon)` or failure |
| `GET /meta/zona?lat=&lon=` (API) | PIP only → `zona_omi` \| `null` |
| Zone select in Streamlit | Prefill from resolve; always overrideable |

Do **not** put Nominatim inside the OMI loader or training pipeline.

## Limits and alternatives

- Ambiguous or incomplete addresses may geocode to the wrong place → manual override is mandatory UX.
- Public Nominatim is shared; for heavy production traffic use a **self-hosted** Nominatim or a commercial geocoder (e.g. Google) with an API key — out of scope for the minimal G4 wire.

## Attribution

Map / geocode data: © OpenStreetMap contributors.  
OMI zones: «Agenzia Entrate – OMI».
