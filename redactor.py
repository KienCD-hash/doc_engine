import sys
from pathlib import Path
import re
import subprocess
from PIL import Image, ImageDraw
import pymupdf
from ocrmac import ocrmac

# 1. Sensible Muster (Blacklist)
PII_PATTERNS = [
    re.compile(r"\b[A-Z]{2}\d{2}[0-9\s]{10,28}\b", re.IGNORECASE),       # IBAN
    re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),              # BIC
    # Telefon / Fax / Mobil
    re.compile(r"\b(?:\+49|0)[0-9\s\/\-\.]{6,25}\b"),
    # E-Mail
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    re.compile(r"\b(?:Inh\.?|Inhaber|Geschäftsführer|Herr|Frau)\b",
               re.IGNORECASE),  # Personalien
    re.compile(r"\b(?:Schwab|Axel\s+Hille|Abed\s+Arabi|Ali\s+Arabi)\b",
               re.IGNORECASE),  # Klarnamen
    # Kassenpersonal
    re.compile(
        r"\b(?:Bediener|Bed\.?|Kassierer(?:in)?)\s*[:#-]?\s*\d+\b", re.IGNORECASE),
]

# 2. Geschützte Rechnungsdaten (Whitelist: NIEMALS schwärzen!)
WHITELIST_PATTERNS = [
    re.compile(
        r"\b(?:Rech(?:nung)?|Rechnungs-?nr|Beleg|Bon|Datum|Summe|Total|EUR|€|Netto|MwSt|Brutto)\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\.\d{1,2}\.(?:20\d{2}|\d{2})\b"),  # Datum
]


def is_sensitive(text: str) -> bool:
    """Prüft, ob ein Text geschwärzt werden muss und nicht auf der Whitelist steht."""
    if not text or len(text.strip()) < 2:
        return False

    # Whitelist-Check: Ist es ein heiliges Rechnungsfeld?
    for w_pat in WHITELIST_PATTERNS:
        if w_pat.search(text):
            return False

    # Blacklist-Check: Passt es auf sensible Daten?
    for p_pat in PII_PATTERNS:
        if p_pat.search(text):
            return True

    return False


def redact_image(input_path: Path, output_path: Path) -> int:
    """Schwärzt ein Bild (JPG, PNG, HEIC) pixelgenau über Apple Vision Bounding Boxes."""
    temp_jpg = None
    work_path = input_path

    # HEIC temporär für OCR konvertieren
    if input_path.suffix.lower() == ".heic":
        temp_jpg = input_path.parent / f"_temp_{input_path.stem}.jpg"
        subprocess.run(
            ["sips", "-s", "format", "jpeg",
                str(input_path), "--out", str(temp_jpg)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        work_path = temp_jpg

    im = Image.open(work_path).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im)

    results = ocrmac.OCR(str(work_path)).recognize()
    redacted_count = 0

    for text, conf, bbox in results:
        if is_sensitive(text):
            x, y, w, h = bbox
            # Apple Vision (Origin unten-links) -> Pillow (Origin oben-links)
            # Mit 4px Padding für vollständige Abdeckung
            left = max(0, int(x * W) - 4)
            top = max(0, int((1.0 - y - h) * H) - 3)
            right = min(W, int((x + w) * W) + 4)
            bottom = min(H, int((1.0 - y) * H) + 3)

            draw.rectangle([left, top, right, bottom], fill="black")
            redacted_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(output_path, quality=95)

    if temp_jpg and temp_jpg.exists():
        temp_jpg.unlink()

    return redacted_count


def redact_pdf(input_path: Path, output_path: Path) -> int:
    """Schwärzt ein PDF direkt im Dokumenten-Stream über PyMuPDF Redactions."""
    doc = pymupdf.open(input_path)
    redacted_count = 0

    for page in doc:
        for pat in PII_PATTERNS:
            matches = re.finditer(pat, page.get_text())
            for m in matches:
                word = m.group(0).strip()
                if len(word) >= 3:
                    rects = page.search_for(word)
                    for r in rects:
                        page.add_redact_annot(r, fill=(0, 0, 0))
                        redacted_count += 1
        page.apply_redactions()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return redacted_count


def redact_file(input_file: Path, output_file: Path) -> int:
    suffix = input_file.suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".heic"]:
        return redact_image(input_file, output_file)
    elif suffix == ".pdf":
        return redact_pdf(input_file, output_file)
    else:
        print(f"Format {suffix} nicht unterstützt für: {input_file.name}")
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Verwendung: python redactor.py <datei_oder_ordner> [output_ordner]")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("anonymisiert")

    if in_path.is_file():
        out_target = out_dir / in_path.name if out_dir.is_dir() else out_dir
        count = redact_file(in_path, out_target)
        print(
            f"Fertig: {count} sensible Stellen in '{in_path.name}' geschwärzt -> '{out_target}'")
    elif in_path.is_dir():
        out_dir.mkdir(parents=True, exist_ok=True)
        files = [p for p in in_path.iterdir() if p.suffix.lower() in [
            ".jpg", ".jpeg", ".png", ".heic", ".pdf"]]
        print(f"Starte Schwärzung über {len(files)} Dokumente...")
        total_boxes = 0
        for f in files:
            target = out_dir / f.name
            cnt = redact_file(f, target)
            total_boxes += cnt
            print(f"  [OK] {f.name}: {cnt} Schwärzungen")
        print(
            f"\nGesamtergebnis: {len(files)} Dokumente verarbeitet, {total_boxes} sensible Stellen unkenntlich gemacht.")
