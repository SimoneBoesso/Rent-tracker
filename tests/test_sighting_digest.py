from api.sighting_digest import sighting_digest


def test_sighting_digest_same_address_dirty_vs_clean() -> None:
    # "v." / spazi / case / civico 05 vs 5 → stesso immobile
    a = sighting_digest("Roma", "00153", "v. Roma", "05")
    b = sighting_digest("roma", "00153", "Via Roma", "5")
    c = sighting_digest("  Roma ", "00153", "  VIA   ROMA ", "5")
    assert a == b == c


def test_sighting_digest_different_civico() -> None:
    assert sighting_digest("Roma", "00153", "Via Roma", "5") != sighting_digest(
        "Roma", "00153", "Via Roma", "6"
    )
    # suffisso unità → digest diverso da solo numero
    assert sighting_digest("Roma", "00153", "Via Roma", "10") != sighting_digest(
        "Roma", "00153", "Via Roma", "10/a"
    )


def test_sighting_digest_abbrev_corso_piazza() -> None:
    assert sighting_digest("Roma", "00186", "c.so Vittorio Emanuele II", "1") == sighting_digest(
        "Roma", "00186", "Corso Vittorio Emanuele II", "1"
    )
    assert sighting_digest("Roma", "00186", "p.zza Navona", "1") == sighting_digest(
        "Roma", "00186", "Piazza Navona", "1"
    )
