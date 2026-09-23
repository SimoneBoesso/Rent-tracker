from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from api.cloud_store import cloud_configured, download_sightings_jsonl
from api.sightings_db import SightingsDB
from etl.jsonl import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
SIGHTINGS_PATH = ROOT / "data/raw/sightings/sightings.jsonl"


class SightingsDriftReport:
    def __init__(self, data: list[dict[str, Any]], *, source: str):
        self.data = data
        self.source = source

    @classmethod
    def from_database(cls, database_url: str) -> SightingsDriftReport:
        rows = SightingsDB(database_url).fetch_drift_rows()
        return cls(rows, source=f"postgres:{database_url.split('@')[-1]}")

    @classmethod
    def from_jsonl(cls, path: Path) -> SightingsDriftReport:
        return cls(load_jsonl(path), source=str(path))

    def build(self, reports_dir: Path) -> dict:
        _reference_rows, current_rows = self.temporal_split(self.data)
        metrics = self.extract_metrics(current_rows)
        self.save(metrics, reports_dir)
        return metrics

    def temporal_split(
        self, data: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        current_rows: list[dict[str, Any]] = []
        reference_rows: list[dict[str, Any]] = []
        for entry in data:
            submitted_at = entry["submitted_at"]
            if isinstance(submitted_at, str):
                submitted_at = datetime.fromisoformat(submitted_at)
            if submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            if submitted_at >= datetime.now(timezone.utc) - timedelta(days=30):
                current_rows.append(entry)
            else:
                reference_rows.append(entry)

        if len(current_rows) < 20:
            raise ValueError("Not enough samples in the current period")

        return reference_rows, current_rows

    def extract_metrics(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        mae = []
        bias = []

        for row in rows:
            predicted_price_per_m2_monthly = row["predicted_price_per_m2_monthly"]
            asking_eur_m2 = row["asking_eur_m2"]
            drift = asking_eur_m2 - predicted_price_per_m2_monthly
            mae.append(abs(drift))
            bias.append(drift)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": self.source,
            "n_samples": len(rows),
            "mae": mean(mae),
            "bias": mean(bias),
        }

    def save(self, metrics: dict[str, Any], reports_dir: Path) -> None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = reports_dir / f"SightingsDriftReport_{run_id}"
        out_dir.mkdir(parents=True, exist_ok=True)

        summary_path = out_dir / "summary.json"
        summary_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        latest_dir = reports_dir / "sightings_drift_latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        (latest_dir / "summary.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sightings drift report (asking vs fair).")
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Legacy: download sightings.jsonl from R2 (only if DATABASE_URL unset)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=SIGHTINGS_PATH,
        help="Legacy JSONL path when DATABASE_URL is unset",
    )
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        report = SightingsDriftReport.from_database(database_url)
    else:
        path = args.input
        need_pull = args.pull or not path.is_file() or path.stat().st_size == 0
        if need_pull:
            if not cloud_configured():
                raise SystemExit(
                    f"DATABASE_URL unset; sightings file missing/empty at {path} "
                    "and cloud is not configured (set DATABASE_URL or AWS_* / --input)."
                )
            if not download_sightings_jsonl(path):
                raise SystemExit(f"Failed to pull sightings.jsonl from R2 → {path}")
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(
                f"DATABASE_URL unset and no legacy sightings data at {path}"
            )
        report = SightingsDriftReport.from_jsonl(path)

    report.build(args.reports_dir)


if __name__ == "__main__":
    main()
