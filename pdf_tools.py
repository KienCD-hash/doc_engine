import sys
from pathlib import Path
import pymupdf
from PIL import Image
import subprocess


def split_pdf(pdf_path: Path, output_dir: Path, dpi: int = 200, as_images: bool = True) -> int:
    """
    Zerlegt eine mehrseitige PDF-Datei in Einzelseiten.
    Standardmäßig als gestochen scharfe PNG-Bilder (ideal für inbox/ und OCR).
    """
    if not pdf_path.exists():
        print(f"Fehler: Datei '{pdf_path}' nicht gefunden!")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Öffne '{pdf_path.name}' ({total_pages} Seiten)...")

    for i, page in enumerate(doc):
        page_num = i + 1
        base_name = f"{pdf_path.stem}_seite_{page_num:02d}"

        if as_images:
            # Als Bild rendern (perfekt für Apple Vision OCR & Fast-Path)
            pix = page.get_pixmap(dpi=dpi)
            out_file = output_dir / f"{base_name}.png"
            pix.save(str(out_file))
        else:
            # Als 1-seitige PDF speichern
            single_doc = pymupdf.open()
            single_doc.insert_pdf(doc, from_page=i, to_page=i)
            out_file = output_dir / f"{base_name}.pdf"
            single_doc.save(str(out_file))
            single_doc.close()

        print(f"  [Seite {page_num:02d}/{total_pages:02d}] -> {out_file.name}")

    doc.close()
    print(f"Erfolgreich {total_pages} Seiten in '{output_dir}' abgelegt.\n")
    return total_pages


def merge_documents(input_paths: list[Path], output_pdf: Path) -> int:
    """
    Klebt mehrere PDFs und Bilder (PNG, JPG, HEIC) zu einer einzigen Sammel-PDF zusammen.
    Ideal für Monatsabschlüsse und Steuerberater-Exporte.
    """
    merged_doc = pymupdf.open()
    count = 0

    for path in input_paths:
        if not path.is_file():
            continue

        ext = path.suffix.lower()

        if ext == ".pdf":
            # PDF anhängen
            src_pdf = pymupdf.open(path)
            merged_doc.insert_pdf(src_pdf)
            src_pdf.close()
            count += 1
            print(f"  [PDF hinzugefügt] {path.name}")

        elif ext in [".png", ".jpg", ".jpeg"]:
            # Bild als eigene PDF-Seite einbetten
            img = Image.open(path)
            w, h = img.size
            rect = pymupdf.Rect(0, 0, w, h)
            page = merged_doc.new_page(width=w, height=h)
            page.insert_image(rect, filename=str(path))
            count += 1
            print(f"  [Bild hinzugefügt] {path.name}")

        elif ext == ".heic":
            # HEIC temporär für PDF-Einbettung wandeln
            temp_jpg = path.parent / f"_temp_merge_{path.stem}.jpg"
            subprocess.run(
                ["sips", "-s", "format", "jpeg",
                    str(path), "--out", str(temp_jpg)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            img = Image.open(temp_jpg)
            w, h = img.size
            rect = pymupdf.Rect(0, 0, w, h)
            page = merged_doc.new_page(width=w, height=h)
            page.insert_image(rect, filename=str(temp_jpg))
            temp_jpg.unlink(missing_ok=True)
            count += 1
            print(f"  [HEIC konvertiert & hinzugefügt] {path.name}")

    if count == 0:
        print("Keine gültigen Belege zum Zusammenkleben gefunden!")
        return 0

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    merged_doc.save(str(output_pdf))
    merged_doc.close()
    print(
        f"\nErfolg: {count} Belege zu einer Sammel-PDF zusammengeklebt -> '{output_pdf}'\n")
    return count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Verwendung:")
        print("  1. PDF trennen (Split):")
        print("     python pdf_tools.py split <stapel.pdf> [ziel_ordner]")
        print("     Beispiel: python pdf_tools.py split scan.pdf inbox/")
        print("")
        print("  2. Belege zusammenkleben (Merge):")
        print(
            "     python pdf_tools.py merge <ausgabe.pdf> <datei1> [datei2 ...]")
        print(
            "     Beispiel: python pdf_tools.py merge monatsbericht.pdf archiv/rechnungen/*")
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "split":
        pdf_file = Path(sys.argv[2])
        target_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("inbox")
        split_pdf(pdf_file, target_dir)

    elif action == "merge":
        out_file = Path(sys.argv[2])
        in_files = [Path(p) for p in sys.argv[3:]]
        expanded_files = []
        for p in in_files:
            if p.is_dir():
                expanded_files.extend(sorted(p.iterdir()))
            else:
                expanded_files.append(p)

        merge_documents(expanded_files, out_file)

    else:
        print(f"Unbekannte Aktion '{action}'. Erlaubt sind: split, merge")
