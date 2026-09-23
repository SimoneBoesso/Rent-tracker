import re
import unicodedata
import hashlib

def normalize_text(text: str) -> str:
    # 1) fold accenti: "à" → "a" (NFKD spezza base+mark; scarti i combining)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # 2) lower + togli . e , (il resto della punteggiatura lo puoi lasciare per ora)
    text = text.lower().replace(".", "").replace(",", "")

    # 3) trim + collasso spazi multipli → uno
    text = re.sub(r"\s+", " ", text.strip())

    return text


_ABBREV = {
    "v": "via",
    "cso": "corso",
    "pzza": "piazza",
}

def normalize_via(via: str) -> str:
    text = normalize_text(via)
    if not text:
        return text
    parts = text.split(" ")
    parts[0] = _ABBREV.get(parts[0], parts[0])  # solo primo token
    return " ".join(parts)



def normalize_civico(s: str) -> str:
    # normalize_text + togli zeri a sinistra ("05"→"5"); tieni suffisso ("5/a")
    text = normalize_text(s)
    if not text:
        return text
    m = re.match(r"^0*(\d+)(.*)$", text)
    if m:
        return m.group(1) + m.group(2)
    return text


def sighting_digest(comune: str, cap: str, via: str, civico: str) -> str:
    comune = normalize_text(comune)
    cap = normalize_text(cap)
    via = normalize_via(via)
    civico = normalize_civico(civico)
    return hashlib.sha256(f"{comune}|{cap}|{via}|{civico}".encode()).hexdigest()