from pathlib import Path
from PIL import Image
import pymupdf
from ocrmac import ocrmac
import subprocess


def extract_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    full_text = ""

    for page in doc:
        text = page.get_text()

        # Haben wir echten digitalen Text? ( mit mehr als 20 Seiten?)
        if len(text.strip()) > 20:
            full_text += text + "\n"
        else:
            # Fallback: Seite ist ein Scan -> als Bild redern & durch OCR jagen
            pix = page.get_pixmap(dpi=150)
            pix.save("temp_page.png")
            full_text += extract_image_ocr("temp_page.png") + "\n"

    doc.close()
    return full_text


def extract_image_ocr(image_path):
    results = ocrmac.OCR(image_path).recognize()

    full_text = ""
    for item in results:
        full_text += item[0] + "\n"

    return full_text


def extract_text(file_path):
    path = Path(file_path)
    endung = path.suffix.lower()

    # Fall 1: iPhone HEIC-Fotos vollautomatisch & lautlos konvertieren
    if endung == ".heic":
        temp_jpg = "temp_heic.jpg"
        subprocess.run(
            ["sips", "-s", "format", "jpeg",
                str(file_path), "--out", temp_jpg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        text = extract_image_ocr(temp_jpg)
        Path(temp_jpg).unlink(missing_ok=True)  # Temporäres Bild aufräumen
        return text

    # Fall 2: Bildateien direkt an die OCR geben
    if endung in [".jpg", ".jpeg", ".png", ".tiff"]:
        return extract_image_ocr(file_path)

    # Fall 3: Digitale PDFs auslesen
    if endung == ".pdf":
        return extract_pdf(file_path)

    # Unbekannte Formats
    return ""


if __name__ == "__main__":
    # 1. Ein schnelles Test-PDF im Speicher erzeugen/ erstellen
    test_doc = pymupdf.open()
    page = test_doc.new_page()
    page.insert_text(
        (50, 72), "Rechnung Nr. 1001\nBetrag: 250,00 EUR\nStatus: Bezahlt")
    test_doc.save("test.pdf")
    test_doc.close()

    # 2. Unsere neue Funktion aufrufen
    ergebnis = extract_pdf("test.pdf")
    print("--- Extrahierter Text ---")
    print(ergebnis)
    print(len(ergebnis))
    if "Bezahlt" in ergebnis:
        print("Status-Check: Rechnung ist bezahlt.")
    else:
        print("Status-Check: Noch offen")

    # 3. Einen Scan simulieren ( PDF-Seite als Bild speichern)
    doc = pymupdf.open("test.pdf")
    doc[0].get_pixmap(dpi=150).save("test.png")
    doc.close()

    # 4. OCR aufrufen und Rohdaten inspizieren
    ocr_daten = extract_image_ocr("test.png")
    print("--- OCR Rohdaten ---")
    print(ocr_daten)
    if "Bezahlt" in ocr_daten:
        print("OCR-Check: Rechnung ist bezahlt.")
    else:
        print("OCR-Check: Rechnung ist noch offen.")

    # 5. Den Dispatcher testen (Eine einzige Funktion für alles)
    print("--- Dispatcher-Test ---")
    print("Aus PDF:")
    print(extract_text("test.pdf"))

    print("Aus Bild:")
    print(extract_text("test.png"))

    # 6. Ein stummes Scanner -PDF erzeugen ( nur Bild, 0 Zeichen Text)
    scan_pdf = pymupdf.open()
    scan_page = scan_pdf.new_page()
    scan_page.insert_image(scan_page.rect, filename="test.png")
    scan_pdf.save("test_scan.pdf")
    scan_pdf.close()

    # 7. Härtetest: Knack die Poststelle auch das stumme PDF?
    print("--- Härtetest: Stummes PDF ---")
    print(extract_text("test_scan.pdf"))
