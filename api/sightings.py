from pathlib import Path
import json
from typing import Any
import logging
import os

logger = logging.getLogger(__name__)

from api.sighting_digest import sighting_digest
from api.sightings_db import SightingsDB
ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DIR = ROOT / "data" / "raw" / "sightings"
DEFAULT_PATH = DEFAULT_DIR / "sightings.jsonl"


# this is called from the API endpoint
def append_sighting(record: dict[str, Any]) -> tuple[str, str|None]:
    return SightingsManager().append_sighting(record)        


class SightingsManager:
    def __init__(self):
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required")
        self.db = SightingsDB(url)
        self.db.init_schema()

    def append_sighting(self, record: dict[str, Any]) -> tuple[str, str|None]:
        digest = sighting_digest(record["comune"], record["cap"], record["via"], record["civico"])
        record["digest"] = digest
        result, existing_id = self.db.add_sighting(record)
        return (result, existing_id)
