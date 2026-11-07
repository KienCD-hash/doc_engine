import time
from pathlib import Path
from tse import scan_tse
from extractor import extract_text
from parser import parse_invoice

# 1. Konfiguration & Pfade
ARCHIVE_DIRS = [
    Path("archiv/rechungen"),
    Path("archiv/rechnungen")
]
CACHE_DIR = Path(".cache_ocr")
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".heic"}

# 2. Golden Master: Bekannte Soll-Werte für kritische Belege
GOLDEN_MASTER = {
    "IMG_0860.heic": {
        "expected_amount": 11.94,
        "note": "Penny (Soll 11,94 EUR Zahlung erfolgt)"
    },
    "IMG_0894.heic": {
        "expected_amount": 23.03,
        "note": "Kaufland (Soll 23,03 EUR Summe/Kartenzahlung)"
    },
    "WhatsApp Image 2026-10-28 at 16.44.43.jpeg": {
        "expected_amount": 58.50,
        "note": "ELAN Tankstelle (Soll 58,50 EUR Sprit statt 70,00 EUR Bar gegeben)"
    },
    "IMG_0838.heic": {
        "expected_amount": 5.93,
        "note": "Lidl (Soll 5,93 EUR Zahlbetrag statt 10,00 EUR Bar)"
    },
    "IMG_0842.heic": {
        "expected_amount": 121.10,
        "note": "Lidl (Soll 121,10 EUR Einkauf statt 221,10 EUR mit Bargeldabhebung)"
    },
    "IMG_0859.heic": {
        "expected_amount": 9.02,
        "note": "Kaufland (Soll 9,02 EUR Brutto-Summe statt 7,38 EUR Netto-Teilbetrag)"
    },
    "IMG_0869.heic": {
        "expected_amount": 4.40,
        "note": "BackWerk (Soll 4,40 EUR statt 7,00 % MwSt)"
    },
    "IMG_0870.heic": {
        "expected_amount": 3.90,
        "note": "BackWerk (Soll 3,90 EUR statt 7,00 % MwSt)"
    },
    "IMG_0880.heic": {
        "expected_amount": 11.34,
        "note": "Penny (Soll 11,34 EUR Brutto)"
    },
    "IMG_0883.heic": {
        "expected_amount": 59.98,
        "note": "Hellweg (Soll 59,98 EUR Brutto)"
    },
    "IMG_0888.heic": {
        "expected_amount": 25.83,
        "note": "Lidl (Soll 25,83 EUR Brutto statt 2,61 EUR Rabatt)"
    },
    "IMG_0889.heic": {
        "expected_amount": 11.40,
        "note": "BackWerk (Soll 11,40 EUR Rechnungsbetrag statt 50,40 EUR Bar)"
    },
    "IMG_0890.heic": {
        "expected_amount": 340.46,
        "note": "kfzteile24 (Soll 340,46 EUR Brutto)"
    }
}
# Farben für das Terminal
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"


def get_cached_raw_text(file_path: Path) -> str:
    """
    Holt den extrahierten Text aus dem Cache (.cache_ocr/).
    Falls noch nicht gecacht, wird die OCR einmalig ausgeführt und gespeichert.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{file_path.name}.txt"

    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    # Noch nicht im Cache -> einmalig OCR durchführen und wegspeichern
    print(f"  [OCR-Initialisierung] Lese {file_path.name} erstmalig ein...")
    text = extract_text(str(file_path))
    cache_file.write_text(text, encoding="utf-8")
    return text


def run_tests():
    start_time = time.perf_counter()

    # Alle Belege aus den Archiv-Ordnern einsammeln
    files = []
    for archive_dir in ARCHIVE_DIRS:
        if archive_dir.exists():
            for file in sorted(archive_dir.iterdir()):
                if file.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(file)

    if not files:
        print("Keine Belege in den Archiv-Ordnern gefunden!")
        return

    print(f"\nStarte Flotten-Testlauf über {len(files)} Archiv-Belege...\n")
    print(f"{'Status':<8} | {'Datei':<22} | {'Rechnungs-Nr':<18} | {'Datum':<10} | {'Betrag':<10} | {'Hinweis'}")
    print("-" * 95)

    passed = 0
    failed = 0

    for file in files:
        # Stufe 1: TSE Fast-Path (KassenSichV QR-Code)
        facts = scan_tse(str(file))

        # Stufe 2: OCR Fallback (Apple Vision + Kassen-Mathematik)
        if not facts:
            raw_text = get_cached_raw_text(file)
            facts = parse_invoice(raw_text)

        status = "PASS"
        reason = ""

        # Grundprüfung: Konnte überhaupt geparst werden?
        if not facts:
            status = "FAIL"
            reason = "Parser liefert None"
        elif not facts.get("invoice_number"):
            status = "FAIL"
            reason = "Keine Rechnungsnummer"
        elif not facts.get("date"):
            status = "FAIL"
            reason = "Kein Datum"
        elif facts.get("total_amount") is None or facts.get("total_amount") <= 0:
            status = "FAIL"
            reason = "Ungültiger Betrag"

        # Golden-Master-Prüfung: Falls feste Soll-Werte hinterlegt sind
        if facts and file.name in GOLDEN_MASTER:
            expected = GOLDEN_MASTER[file.name]["expected_amount"]
            actual = round(facts.get("total_amount", 0.0), 2)
            if actual != expected:
                status = "FAIL"
                reason = f"Betrag {actual:.2f} != Soll {expected:.2f} ({GOLDEN_MASTER[file.name]['note']})"

        # Ausgabezeile formatieren
        if status == "PASS":
            passed += 1
            status_display = f"{COLOR_GREEN}PASS{COLOR_RESET}    "
        else:
            failed += 1
            status_display = f"{COLOR_RED}FAIL{COLOR_RESET}    "

        inv_nr = facts.get("invoice_number", "-") if facts else "-"
        inv_date = facts.get("date", "-") if facts else "-"
        amount = f"{facts.get('total_amount'):.2f} €" if facts and facts.get(
            "total_amount") is not None else "-"

        # Gekürzter Dateiname für saubere Tabellenspalten
        display_name = file.name if len(
            file.name) <= 22 else file.name[:19] + "..."

        print(f"{status_display} | {display_name:<22} | {inv_nr:<18} | {inv_date:<10} | {amount:<10} | {reason}")

    elapsed = time.perf_counter() - start_time
    print("-" * 95)
    print(f"Laufzeit: {elapsed:.3f} Sekunden | Gesamt: {len(files)} | {COLOR_GREEN}Bestanden: {passed}{COLOR_RESET} | {COLOR_RED}Fehlgeschlagen: {failed}{COLOR_RESET}\n")


if __name__ == "__main__":
    run_tests()
