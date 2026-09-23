from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.sighting_digest import sighting_digest
from api.sightings import append_sighting
from api.sightings_db import SightingsDB
from tests.test_api import _tiny_model

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


def _addr(**overrides: str) -> dict[str, str]:
    base = {
        "comune": "Roma",
        "cap": "00153",
        "via": f"Via Test {uuid.uuid4().hex[:8]}",
        "civico": "1",
    }
    base.update(overrides)
    return base


def _record(**overrides) -> dict:
    addr = _addr()
    row = {
        "sighting_id": str(uuid.uuid4()),
        "submitted_at": datetime.now(timezone.utc),
        "source": "user",
        "zona_omi": "B12",
        "tipologia": "Abitazioni civili",
        "stato": "NORMALE",
        "asking_eur_m2": 18.0,
        "predicted_price_per_m2_monthly": 20.0,
        "gap_pct": -10.0,
        "deal_label": "fair",
        "deal_basis": "omi_band",
        **addr,
    }
    row.update(overrides)
    return row


def test_append_sighting_duplicate_same_digest() -> None:
    first = _record()
    second = {**first, "sighting_id": str(uuid.uuid4()), "asking_eur_m2": 99.0}
    assert append_sighting(first) == ("ok", None)
    status, dup_of = append_sighting(second)
    assert status == "duplicate"
    assert dup_of == first["sighting_id"]


def test_append_sighting_concurrent_same_digest() -> None:
    addr = _addr()
    records = [_record(**addr, sighting_id=str(uuid.uuid4())) for _ in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append_sighting, records))

    oks = [r for r in results if r[0] == "ok"]
    dups = [r for r in results if r[0] == "duplicate"]
    assert len(oks) == 1
    assert len(dups) == 7
    winner_id = next(
        rec["sighting_id"] for rec, status in zip(records, results) if status[0] == "ok"
    )
    assert all(d[1] == winner_id for d in dups)

    digest = sighting_digest(addr["comune"], addr["cap"], addr["via"], addr["civico"])
    db = SightingsDB(os.environ["DATABASE_URL"])
    assert db.get_by_digest(digest) == winner_id


def test_sighting_upload(tmp_path: Path) -> None:
    features = tmp_path / "features.jsonl"
    rows = [
        {
            "zona_omi": "B12",
            "tipologia": "Abitazioni civili",
            "stato": "NORMALE",
            "semester": "2025-1",
            "price_per_m2_monthly": 10,
        }
    ]
    features.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    model_path = _tiny_model(tmp_path)
    suffix = uuid.uuid4().hex[:8]
    addr = _addr(via=f"v. Upload {suffix}", civico="05")
    payload = {
        "zona_omi": "B12",
        "tipologia": "Abitazioni civili",
        "stato": "NORMALE",
        "asking_eur_m2": 10,
        **addr,
    }
    dirty = {
        **payload,
        "via": f"Via Upload {suffix}",
        "civico": "5",
        "asking_eur_m2": 99.0,
    }

    with TestClient(create_app(model_path, features_path=features)) as client:
        resp1 = client.post("/sightings", json=payload)
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["status"] == "ok"
        assert body1["duplicate_of"] is None

        resp2 = client.post("/sightings", json=dirty)
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["status"] == "duplicate"
        assert body2["duplicate_of"] == body1["sighting_id"]
