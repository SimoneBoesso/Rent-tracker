import psycopg


class SightingsDB:
    def __init__(self, db_url: str):
        self.db_url = db_url

    def init_schema(self) -> None:
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sightings (
                        digest TEXT PRIMARY KEY,
                        sighting_id TEXT NOT NULL,
                        submitted_at TIMESTAMPTZ NOT NULL,
                        source TEXT,
                        zona_omi TEXT NOT NULL,
                        tipologia TEXT NOT NULL,
                        stato TEXT NOT NULL,
                        asking_eur_m2 DOUBLE PRECISION NOT NULL,
                        predicted_price_per_m2_monthly DOUBLE PRECISION,
                        gap_pct DOUBLE PRECISION,
                        deal_label TEXT,
                        deal_basis TEXT,
                        comune TEXT NOT NULL,
                        cap TEXT NOT NULL,
                        via TEXT NOT NULL,
                        civico TEXT NOT NULL,
                        interno TEXT,
                        n_bagni INTEGER,
                        n_locali INTEGER,
                        mq DOUBLE PRECISION,
                        piano INTEGER,
                        ascensore BOOLEAN,
                        arredato BOOLEAN,
                        balcone BOOLEAN,
                        terrazzo BOOLEAN
                    )
                    """
                )
                conn.commit()

    def get_by_digest(self, digest: str) -> str | None:
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT sighting_id FROM sightings WHERE digest = %s",
                    (digest,),
                )
                row = cursor.fetchone()
                return row[0] if row else None

    def fetch_drift_rows(self) -> list[dict]:
        """Rows needed by sightings drift (asking vs fair)."""
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT submitted_at, asking_eur_m2, predicted_price_per_m2_monthly
                    FROM sightings
                    ORDER BY submitted_at
                    """
                )
                return [
                    {
                        "submitted_at": submitted_at,
                        "asking_eur_m2": float(asking),
                        "predicted_price_per_m2_monthly": float(predicted)
                        if predicted is not None
                        else None,
                    }
                    for submitted_at, asking, predicted in cursor.fetchall()
                ]

    def add_sighting(self, sighting: dict) -> tuple[str, str | None]:
        cols = (
            "digest",
            "sighting_id",
            "submitted_at",
            "source",
            "zona_omi",
            "tipologia",
            "stato",
            "asking_eur_m2",
            "predicted_price_per_m2_monthly",
            "gap_pct",
            "deal_label",
            "deal_basis",
            "comune",
            "cap",
            "via",
            "civico",
            "interno",
            "n_bagni",
            "n_locali",
            "mq",
            "piano",
            "ascensore",
            "arredato",
            "balcone",
            "terrazzo",
        )
        placeholders = ", ".join(["%s"] * len(cols))
        values = tuple(sighting.get(c) for c in cols)

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO sightings ({", ".join(cols)})
                    VALUES ({placeholders})
                    ON CONFLICT (digest) DO NOTHING
                    RETURNING sighting_id
                    """,
                    values,
                )
                row = cursor.fetchone()
                conn.commit()

        if row is not None:
            return ("ok", None)

        existing_id = self.get_by_digest(sighting["digest"])
        return ("duplicate", existing_id)
