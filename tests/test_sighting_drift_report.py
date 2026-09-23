from datetime import datetime, timezone

from ml.sightings_drift_report import SightingsDriftReport
from pathlib import Path


def test_sightings_drift_report(tmp_path: Path):
    rows = _sighting_rows(n=21)
    report = SightingsDriftReport(rows, source="test-rows")
    metrics = report.build(reports_dir=tmp_path / "reports")
    assert metrics["mae"] == 0
    assert metrics["bias"] == 0
    assert metrics["n_samples"] == 21
    assert metrics["input"] == "test-rows"

    assert (tmp_path / "reports" / "sightings_drift_latest" / "summary.json").is_file()


def _sighting_rows(n: int = 21) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "submitted_at": now,
            "predicted_price_per_m2_monthly": 1000,
            "asking_eur_m2": 1000,
        }
        for _ in range(n)
    ]
