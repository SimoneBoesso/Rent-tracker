import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Rent-tracker/0.1 (local-dev)"  # obbligatorio

def geocode_address(address: str) -> tuple[float, float] | None:
    q = address.strip()
    if not q:
        return None

    with  httpx.Client(timeout=10) as client:
        resp = client.get(NOMINATIM_URL, params={"q": q, "format": "json", "limit": 1, "countrycodes": "it"}, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        hits = resp.json()
        if not hits:
            return None
        return float(hits[0]["lat"]), float(hits[0]["lon"])
